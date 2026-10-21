"""Knowledge base: what each algorithm is, and what a quantum computer does to it.

quantum_status:
  "shor"        broken outright by Shor's algorithm (RSA, finite-field DH, elliptic curves)
  "grover"      security roughly halved by Grover search (128-bit symmetric keys)
  "safe"        no known quantum attack better than Grover at an acceptable level
  "classical"   already broken classically (replace regardless of quantum)
nist_quantum_level follows CycloneDX: 0 = vulnerable, 1-5 = NIST PQC security categories.
"""

import re

ALGORITHMS = {
    # public-key, Shor-vulnerable
    "RSA": {"primitive": "pke", "status": "shor", "replacement": "ML-KEM-768 (encryption) / ML-DSA-65 (signatures)"},
    "ECDSA": {"primitive": "signature", "status": "shor", "replacement": "ML-DSA-65"},
    "EdDSA": {"primitive": "signature", "status": "shor", "replacement": "ML-DSA-65"},
    "ECDH": {"primitive": "key-agree", "status": "shor", "replacement": "X25519MLKEM768 (hybrid)"},
    "X25519": {"primitive": "key-agree", "status": "shor", "replacement": "X25519MLKEM768 (hybrid)"},
    "X448": {"primitive": "key-agree", "status": "shor", "replacement": "X25519MLKEM768 (hybrid)"},
    "DH": {"primitive": "key-agree", "status": "shor", "replacement": "ML-KEM-768"},
    "DSA": {"primitive": "signature", "status": "shor", "replacement": "ML-DSA-65"},
    # post-quantum and hybrid
    "ML-KEM": {"primitive": "kem", "status": "safe", "replacement": None},
    "X25519MLKEM768": {"primitive": "kem", "status": "safe", "replacement": None},
    "ML-DSA": {"primitive": "signature", "status": "safe", "replacement": None},
    "SLH-DSA": {"primitive": "signature", "status": "safe", "replacement": None},
    # symmetric and hashes
    "AES-128": {"primitive": "ae", "status": "grover", "replacement": "AES-256"},
    "AES-192": {"primitive": "ae", "status": "safe", "replacement": None},
    "AES-256": {"primitive": "ae", "status": "safe", "replacement": None},
    "ChaCha20-Poly1305": {"primitive": "ae", "status": "safe", "replacement": None},
    "SHA-256": {"primitive": "hash", "status": "safe", "replacement": None},
    "SHA-384": {"primitive": "hash", "status": "safe", "replacement": None},
    "SHA-512": {"primitive": "hash", "status": "safe", "replacement": None},
    "SHA3": {"primitive": "hash", "status": "safe", "replacement": None},
    # classically broken
    "MD5": {"primitive": "hash", "status": "classical", "replacement": "SHA-256"},
    "SHA-1": {"primitive": "hash", "status": "classical", "replacement": "SHA-256"},
    "DES": {"primitive": "block-cipher", "status": "classical", "replacement": "AES-256"},
    "3DES": {"primitive": "block-cipher", "status": "classical", "replacement": "AES-256"},
    "RC4": {"primitive": "stream-cipher", "status": "classical", "replacement": "AES-256-GCM"},
}

NIST_LEVEL = {"ML-KEM-512": 1, "ML-KEM-768": 3, "ML-KEM-1024": 5, "X25519MLKEM768": 3,
              "ML-DSA-44": 2, "ML-DSA-65": 3, "ML-DSA-87": 5, "AES-128": 1, "AES-192": 3,
              "AES-256": 5, "ChaCha20-Poly1305": 5}

CURVE_ALIASES = {"secp256r1": "P-256", "prime256v1": "P-256", "secp384r1": "P-384",
                 "secp521r1": "P-521", "p-256": "P-256", "p-384": "P-384", "p-521": "P-521"}
CURVE_BITS = {"P-256": 256, "P-384": 384, "P-521": 521, "Curve25519": 255, "Ed25519": 255}


def family_of(name: str) -> str:
    """Map a concrete algorithm name ('RSA-2048', 'ECDSA-P-256') to its catalog family."""
    for fam in sorted(ALGORITHMS, key=len, reverse=True):
        if name.upper().startswith(fam.upper()):
            return fam
    return name


def describe(name: str) -> dict:
    fam = family_of(name)
    info = dict(ALGORITHMS.get(fam, {"primitive": "unknown", "status": "unknown", "replacement": None}))
    info["family"] = fam
    if info["status"] == "shor":
        level = 0
    else:
        level = next((v for k, v in NIST_LEVEL.items() if name.upper().startswith(k.upper())), None)
    info["nist_quantum_level"] = level
    return info


def size_parameter(name: str):
    """Key size in bits for RSA, or the curve bit-length for elliptic-curve algorithms."""
    m = re.match(r"RSA-(\d+)", name)
    if m:
        return ("rsa", int(m.group(1)))
    for curve, bits in CURVE_BITS.items():
        if curve.upper() in name.upper():
            return ("ecc", bits)
    if name.upper().startswith(("X25519", "ED25519", "EDDSA")):
        return ("ecc", 255)
    return None


def normalize_curve(curve: str) -> str:
    return CURVE_ALIASES.get(curve.lower(), curve)
