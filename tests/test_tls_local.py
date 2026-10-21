"""Integration tests: real TLS handshakes against a local server with freshly generated certificates.

No internet needed. Each certificate type is served on 127.0.0.1 and scanned with scan_tls.
"""

import datetime as dt
import shutil
import socket
import ssl
import threading

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from cryptography.x509.oid import NameOID

from qday.catalog import describe
from qday.scanner import tls as tls_scanner
from qday.scanner.cbom import build_cbom

KEYS = {
    "RSA-2048": lambda: rsa.generate_private_key(65537, 2048),
    "RSA-3072": lambda: rsa.generate_private_key(65537, 3072),
    "ECDSA-P-256": lambda: ec.generate_private_key(ec.SECP256R1()),
    "ECDSA-P-384": lambda: ec.generate_private_key(ec.SECP384R1()),
    "EdDSA-Ed25519": lambda: ed25519.Ed25519PrivateKey.generate(),
}


def self_signed(key, tmp_path, name):
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    algo = None if isinstance(key, ed25519.Ed25519PrivateKey) else hashes.SHA256()
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=30))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
            .sign(key, algo))
    cert_path, key_path = tmp_path / f"{name}.crt", tmp_path / f"{name}.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    return cert_path, key_path


class LocalTLSServer:
    def __init__(self, cert, key):
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(cert, key)
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.sock.settimeout(0.5)
        self.port = self.sock.getsockname()[1]
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        while not self.stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except OSError:
                continue
            try:
                conn.settimeout(3)
                with self.ctx.wrap_socket(conn, server_side=True) as tls_conn:
                    try:
                        tls_conn.recv(1)
                    except (OSError, ssl.SSLError):
                        pass
            except (OSError, ssl.SSLError):
                pass

    def close(self):
        self.stop.set()
        self.sock.close()
        self.thread.join(timeout=3)


@pytest.fixture(scope="module", params=list(KEYS))
def server(request, tmp_path_factory):
    name = request.param
    cert, key = self_signed(KEYS[name](), tmp_path_factory.mktemp(name), name)
    srv = LocalTLSServer(str(cert), str(key))
    yield name, srv
    srv.close()


def test_detects_certificate_key(server):
    name, srv = server
    profile = tls_scanner.scan_tls("127.0.0.1", srv.port, timeout=5, verify=False)
    assert profile["certificate_key"] == name


def test_negotiates_modern_tls(server):
    _, srv = server
    profile = tls_scanner.scan_tls("127.0.0.1", srv.port, timeout=5, verify=False)
    assert profile["tls_version"] in ("TLSv1.2", "TLSv1.3")
    assert any(a["purpose"] == "bulk encryption" for a in profile["assets"])


def test_certificate_key_is_classified_quantum_vulnerable(server):
    _, srv = server
    profile = tls_scanner.scan_tls("127.0.0.1", srv.port, timeout=5, verify=False)
    key_asset = next(a for a in profile["assets"] if a["purpose"].startswith("authentication (server"))
    assert describe(key_asset["algorithm"])["status"] == "shor"


def test_verification_rejects_self_signed(server):
    _, srv = server
    with pytest.raises(ssl.SSLError):
        tls_scanner.scan_tls("127.0.0.1", srv.port, timeout=5, verify=True)


def test_scan_feeds_cbom(server):
    name, srv = server
    profile = tls_scanner.scan_tls("127.0.0.1", srv.port, timeout=5, verify=False)
    bom = build_cbom(profile["assets"])
    assert name in {c["name"] for c in bom["components"]}


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl CLI not installed")
def test_openssl_reports_key_exchange_group(server):
    _, srv = server
    profile = tls_scanner.scan_tls("127.0.0.1", srv.port, timeout=5, verify=False)
    assert profile["key_exchange_group"]


def test_closed_port_raises_cleanly():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    with pytest.raises(OSError):
        tls_scanner.scan_tls("127.0.0.1", port, timeout=2, verify=False)


# ---------------------------------------------------------------- pure mapping helpers
@pytest.mark.parametrize("cipher,expected", [
    ("TLS_AES_256_GCM_SHA384", "AES-256-GCM"),
    ("TLS_AES_128_GCM_SHA256", "AES-128-GCM"),
    ("TLS_CHACHA20_POLY1305_SHA256", "ChaCha20-Poly1305"),
    ("ECDHE-RSA-AES256-GCM-SHA384", "AES-256-GCM"),
    ("ECDHE-ECDSA-AES128-GCM-SHA256", "AES-128-GCM"),
    ("ECDHE-RSA-CHACHA20-POLY1305", "ChaCha20-Poly1305"),
    ("AES256-SHA", "AES-256"),
    ("AES128-SHA", "AES-128"),
    ("DES-CBC3-SHA", "DES-CBC3-SHA"),
])
def test_cipher_mapping(cipher, expected):
    assert tls_scanner._cipher_algorithm(cipher) == expected


@pytest.mark.parametrize("group,expected", [
    ("X25519MLKEM768", "X25519MLKEM768"),
    ("SecP256r1MLKEM768", "SecP256r1MLKEM768"),
    ("X25519", "X25519"),
    ("x25519", "X25519"),
    ("secp256r1", "ECDH-P-256"),
    ("prime256v1", "ECDH-P-256"),
    ("secp384r1", "ECDH-P-384"),
    ("secp521r1", "ECDH-P-521"),
])
def test_group_mapping(group, expected):
    assert tls_scanner._group_algorithm(group) == expected


@pytest.mark.parametrize("bad_host", ["-proxy evil:8080", "", "a b", "host;id", "http://", "ftp://x.org"])
def test_scan_rejects_bad_hosts_before_any_network(bad_host):
    from qday.safety import InputError
    with pytest.raises(InputError):
        tls_scanner.scan_tls(bad_host)


@pytest.mark.parametrize("bad_port", [0, -1, 65536, "abc", None])
def test_scan_rejects_bad_ports(bad_port):
    from qday.safety import InputError
    with pytest.raises(InputError):
        tls_scanner.scan_tls("127.0.0.1", bad_port)


@pytest.mark.parametrize("output,expected", [
    ("Negotiated TLS1.3 group: X25519MLKEM768\n", "X25519MLKEM768"),
    ("Peer Temp Key: X25519, 253 bits\n", "X25519"),
    ("Server Temp Key: X25519, 253 bits\n", "X25519"),
    ("Peer Temp Key: ECDH, prime256v1, 256 bits\n", "prime256v1"),
    ("Server Temp Key: ECDH, secp384r1, 384 bits\n", "secp384r1"),
    ("Peer Temp Key: DH, 2048 bits\n", "DH-2048"),
    ("Peer Temp Key: X448, 448 bits\n", "X448"),
    ("no key exchange line here\n", None),
])
def test_parse_key_exchange_across_openssl_versions(output, expected):
    assert tls_scanner.parse_key_exchange(output) == expected


@pytest.mark.parametrize("group,status", [("X25519", "shor"), ("X448", "shor"), ("DH-2048", "shor"),
                                          ("prime256v1", "shor"), ("X25519MLKEM768", "safe")])
def test_every_key_exchange_group_is_classified(group, status):
    assert describe(tls_scanner._group_algorithm(group))["status"] == status
