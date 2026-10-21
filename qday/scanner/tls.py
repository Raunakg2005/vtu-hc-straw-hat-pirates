"""Scan a live TLS endpoint: certificate key, signature, key-exchange group and cipher.

The certificate is read with Python's ssl + cryptography. The negotiated key-exchange group
(e.g. X25519MLKEM768, the hybrid post-quantum group) is not exposed by Python's ssl module,
so it is read from `openssl s_client` (OpenSSL >= 3.5 offers the hybrid group by default).
Only scan hosts you own or are authorised to test.
"""

import re
import shutil
import socket
import ssl
import subprocess

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa

from ..catalog import normalize_curve
from ..safety import validate_host, validate_port


def _cipher_algorithm(cipher_name: str) -> str:
    c = cipher_name.upper()
    if "CHACHA20" in c:
        return "ChaCha20-Poly1305"
    for bits in ("256", "192", "128"):
        if f"AES_{bits}" in c or f"AES{bits}" in c:
            return f"AES-{bits}-GCM" if "GCM" in c else f"AES-{bits}"
    return cipher_name


def _group_algorithm(group: str) -> str:
    g = group.strip()
    if "MLKEM" in g.upper():
        return g  # e.g. X25519MLKEM768, SecP256r1MLKEM768
    if g.upper() in ("X25519", "X448"):
        return g.upper()
    if g.upper().startswith(("DH", "FFDHE")):
        return "DH"
    return f"ECDH-{normalize_curve(g)}"


def parse_key_exchange(s_client_output: str):
    """Key-exchange group from `openssl s_client` output, across OpenSSL versions.

    OpenSSL 3.5 prints "Negotiated TLS1.3 group: X25519MLKEM768" for hybrid groups and
    "Peer Temp Key: X25519, 253 bits" for classic ones; older versions print "Server Temp Key: ...".
    Elliptic-curve and finite-field lines look like "ECDH, prime256v1, 256 bits" / "DH, 2048 bits".
    """
    m = re.search(r"Negotiated TLS1\.3 group:\s*(\S+)", s_client_output)
    if m:
        return m.group(1)
    m = re.search(r"(?:Server|Peer) Temp Key:\s*([^\n]+)", s_client_output)
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(",")]
    if parts[0].upper() == "ECDH" and len(parts) > 1:
        return parts[1]
    if parts[0].upper() == "DH":
        bits = re.search(r"(\d+)", parts[1]) if len(parts) > 1 else None
        return f"DH-{bits.group(1)}" if bits else "DH"
    return parts[0]


def _openssl_handshake(host: str, port: int, timeout: int) -> dict:
    exe = shutil.which("openssl")
    if not exe:
        return {}
    try:
        out = subprocess.run(
            [exe, "s_client", "-connect", f"{host}:{port}", "-servername", host, "-showcerts"],
            input=b"", capture_output=True, timeout=timeout,
        ).stdout.decode("utf8", "replace")
    except (subprocess.TimeoutExpired, OSError):
        return {}
    info = {}
    pems = re.findall(r"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", out, re.S)
    if len(pems) > 1:  # chain[1] is the CA that signed the server certificate
        issuer_cert = x509.load_pem_x509_certificate(pems[1].encode())
        info["issuer_key"] = _key_algorithm(issuer_cert.public_key())
    group = parse_key_exchange(out)
    if group:
        info["group"] = group
    m = re.search(r"Peer signature type:\s*(\S+)", out)
    if m:
        info["peer_signature"] = m.group(1)
    m = re.search(r"OpenSSL\s+([\d.]+)", subprocess.run(
        [exe, "version"], capture_output=True, text=True).stdout)
    info["openssl"] = m.group(1) if m else None
    return info


def _key_algorithm(public_key) -> str:
    if isinstance(public_key, rsa.RSAPublicKey):
        return f"RSA-{public_key.key_size}"
    if isinstance(public_key, ec.EllipticCurvePublicKey):
        return f"ECDSA-{normalize_curve(public_key.curve.name)}"
    if isinstance(public_key, ed25519.Ed25519PublicKey):
        return "EdDSA-Ed25519"
    if isinstance(public_key, ed448.Ed448PublicKey):
        return "EdDSA-Ed448"
    return type(public_key).__name__


def scan_tls(host: str, port: int = 443, timeout: int = 10, verify: bool = True) -> dict:
    """Return the endpoint's cryptographic profile and a list of assets.

    verify=False inspects endpoints with self-signed or internal certificates (inventory mode); the
    certificate is still parsed, it is just not trusted.
    """
    host = validate_host(host)  # also blocks values that openssl would parse as options
    port = validate_port(port)
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            version = tls.version()
            cipher_name = tls.cipher()[0]
            der = tls.getpeercert(binary_form=True)
    cert = x509.load_der_x509_certificate(der)
    key_alg = _key_algorithm(cert.public_key())
    sig_oid = cert.signature_algorithm_oid._name  # e.g. ecdsa-with-SHA384
    handshake = _openssl_handshake(host, port, timeout)
    location = f"{host}:{port}"
    issuer = cert.issuer.rfc4514_string()
    assets = [
        {"algorithm": key_alg, "purpose": "authentication (server certificate key)",
         "location": location, "detail": f"subject {cert.subject.rfc4514_string()}"},
        {"algorithm": handshake.get("issuer_key") or (
            "ECDSA" if "ecdsa" in sig_oid.lower() else "RSA" if "rsa" in sig_oid.lower() else sig_oid),
         "purpose": "authentication (CA signature on certificate)", "location": location,
         "detail": f"{sig_oid} by issuer {issuer}"},
        {"algorithm": _cipher_algorithm(cipher_name), "purpose": "bulk encryption",
         "location": location, "detail": f"{version} {cipher_name}"},
    ]
    if handshake.get("group"):
        assets.append({"algorithm": _group_algorithm(handshake["group"]), "purpose": "key exchange",
                       "location": location, "detail": f"negotiated group {handshake['group']}"})
    return {
        "host": host,
        "port": port,
        "tls_version": version,
        "cipher": cipher_name,
        "certificate_key": key_alg,
        "certificate_signature": sig_oid,
        "certificate_issuer": issuer,
        "certificate_expires": cert.not_valid_after_utc.date().isoformat(),
        "key_exchange_group": handshake.get("group"),
        "peer_signature": handshake.get("peer_signature"),
        "openssl_version": handshake.get("openssl"),
        "assets": assets,
    }
