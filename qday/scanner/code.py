"""Static scan of a source tree for cryptographic algorithm usage.

Pattern-based (regex) detection across Python, JavaScript/TypeScript, Java, Go and config
files. It reports where each algorithm appears so it can be placed in a CBOM; it does not
prove reachability, so findings are leads for review, not verdicts.
"""

import os
import re
from pathlib import Path

from ..safety import InputError

EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".java", ".kt", ".go", ".rs",
              ".cs", ".php", ".rb", ".c", ".cpp", ".h", ".yaml", ".yml", ".json", ".toml",
              ".conf", ".env.example", ".properties", ".xml"}
SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build", ".next",
             "site-packages", "target", "vendor"}

# (algorithm, purpose, regex)
RULES = [
    ("RSA", "public-key crypto", r"rsa\.generate_private_key|RSA\.generate|generateKeyPair(Sync)?\(\s*['\"]rsa|KeyPairGenerator\.getInstance\(\s*\"RSA|rsa\.GenerateKey|\bRSA_?(PKCS1|OAEP|PSS)"),
    ("RSA", "JWT signature", r"\b(RS|PS)(256|384|512)\b"),
    ("ECDSA", "JWT signature", r"\bES(256|384|512)\b"),
    ("ECDSA", "signature", r"ec\.generate_private_key|ECDSA|ecdsa\.GenerateKey|generateKeyPair(Sync)?\(\s*['\"]ec"),
    ("EdDSA", "signature", r"\bEd25519\b|ed25519\.|\bEdDSA\b"),
    ("X25519", "key exchange", r"\bX25519\b|x25519\.|curve25519"),
    ("ECDH", "key exchange", r"\bECDH\b|createECDH|ec\.ECDH"),
    ("DH", "key exchange", r"\bDiffie-?Hellman\b|createDiffieHellman|\bdh\.generate_parameters"),
    ("DSA", "signature", r"\bdsa\.generate_private_key|KeyPairGenerator\.getInstance\(\s*\"DSA"),
    ("AES-128", "symmetric encryption", r"AES[-_]?128|aes-128-|key_size\s*=\s*128|AESGCM\.generate_key\(\s*bit_length\s*=\s*128"),
    ("AES-256", "symmetric encryption", r"AES[-_]?256|aes-256-|AESGCM\.generate_key\(\s*bit_length\s*=\s*256"),
    ("ChaCha20-Poly1305", "symmetric encryption", r"ChaCha20|chacha20"),
    ("MD5", "hash", r"\bmd5\b|MD5\(|hashlib\.md5|createHash\(\s*['\"]md5"),
    ("SHA-1", "hash", r"\bsha1\b|SHA-?1\b|hashlib\.sha1|createHash\(\s*['\"]sha1"),
    ("DES", "symmetric encryption", r"\bDES\b(?!C)|des-cbc|DES\.new"),
    ("3DES", "symmetric encryption", r"3DES|TripleDES|des-ede3|DES3"),
    ("RC4", "symmetric encryption", r"\bRC4\b|ARC4|arcfour"),
    ("ML-KEM", "key encapsulation", r"ML[-_]?KEM|Kyber"),
    ("ML-DSA", "signature", r"ML[-_]?DSA|Dilithium"),
    ("SLH-DSA", "signature", r"SLH[-_]?DSA|SPHINCS"),
]
COMPILED = [(alg, purpose, re.compile(rx, re.IGNORECASE if alg not in ("DES",) else 0))
            for alg, purpose, rx in RULES]


_CURVES = [(re.compile(r"SECP256R1|prime256v1|P-?256\b|\bES256\b", re.I), "P-256"),
           (re.compile(r"SECP384R1|P-?384\b|\bES384\b", re.I), "P-384"),
           (re.compile(r"SECP521R1|P-?521\b|\bES512\b", re.I), "P-521"),
           (re.compile(r"secp256k1", re.I), "secp256k1")]
_RSA_SIZE = re.compile(r"(?:key_?size|modulusLength|bits)\s*[=:]\s*(\d{3,5})|\bRSA[-_ ]?(\d{4})\b", re.I)


def _concrete_name(alg: str, line: str):
    """Attach key size / curve to a generic finding. Returns (name, note)."""
    if alg == "RSA":
        m = _RSA_SIZE.search(line)
        if m:
            return f"RSA-{m.group(1) or m.group(2)}", None
        return "RSA-2048", "key size not visible in code; assumed 2048 (most common)"
    if alg in ("ECDSA", "ECDH"):
        for rx, curve in _CURVES:
            if rx.search(line):
                return f"{alg}-{curve}", None
        return f"{alg}-P-256", "curve not visible in code; assumed P-256 (most common)"
    if alg == "EdDSA":
        return "EdDSA-Ed25519", None
    return alg, None


MAX_FILE_BYTES = 2_000_000
MAX_FILES = 50_000


def _wanted(name: str) -> bool:
    lower = name.lower()
    return Path(lower).suffix in EXTENSIONS or lower.endswith(".env.example")


def _is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return b"\0" in fh.read(8192)
    except OSError:
        return True


def _iter_files(root: Path):
    """Walk without following symlinks (no loops, no escaping the tree), skipping vendored dirs."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS
                             and not os.path.islink(os.path.join(dirpath, d)))
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if not _wanted(name) or path.is_symlink():
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            if not _is_binary(path):
                yield path


def scan_code(root: str, max_findings: int = 2000) -> dict:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise InputError(f"not a folder: {root}")
    findings, files_scanned = [], 0
    for path in _iter_files(root_path):
        files_scanned += 1
        if files_scanned > MAX_FILES:
            return {"root": str(root_path), "files_scanned": files_scanned - 1, "assets": findings,
                    "truncated": True}
        try:
            lines = path.read_text(encoding="utf8", errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            if len(line) > 500:
                continue
            for alg, purpose, rx in COMPILED:
                if rx.search(line):
                    name, note = _concrete_name(alg, line)
                    findings.append({
                        "algorithm": name,
                        "purpose": purpose,
                        "location": f"{path.relative_to(root_path).as_posix()}:{lineno}",
                        "detail": line.strip()[:160] + (f"  [{note}]" if note else ""),
                    })
                    if len(findings) >= max_findings:
                        return {"root": str(root_path), "files_scanned": files_scanned,
                                "assets": findings, "truncated": True}
    return {"root": str(root_path), "files_scanned": files_scanned, "assets": findings, "truncated": False}
