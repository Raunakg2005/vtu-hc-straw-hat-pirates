"""Every detection rule: code that must be found (with the right key size) and code that must not."""

import pytest

from qday.scanner import code as scanner

POSITIVE = [
    # (filename, source line, expected algorithm)
    ("a.py", "key = rsa.generate_private_key(public_exponent=65537, key_size=2048)", "RSA-2048"),
    ("a.py", "key = rsa.generate_private_key(public_exponent=65537, key_size=3072)", "RSA-3072"),
    ("a.py", "key = rsa.generate_private_key(public_exponent=65537, key_size=4096)", "RSA-4096"),
    ("a.js", "crypto.generateKeyPairSync('rsa', { modulusLength: 2048 })", "RSA-2048"),
    ("a.js", 'crypto.generateKeyPairSync("rsa", { modulusLength: 4096 })', "RSA-4096"),
    ("A.java", 'KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");', "RSA-2048"),
    ("a.go", "priv, _ := rsa.GenerateKey(rand.Reader, 2048)", "RSA-2048"),
    ("a.py", "cipher = PKCS1_OAEP.new(key)  # RSA_OAEP", "RSA-2048"),
    ("a.py", 'jwt.encode(claims, key, algorithm="RS256")', "RSA-2048"),
    ("a.py", 'jwt.encode(claims, key, algorithm="PS512")', "RSA-2048"),
    ("a.ts", "jwt.sign(payload, key, { algorithm: 'ES256' })", "ECDSA-P-256"),
    ("a.ts", "jwt.sign(payload, key, { algorithm: 'ES384' })", "ECDSA-P-384"),
    ("a.py", "k = ec.generate_private_key(ec.SECP256R1())", "ECDSA-P-256"),
    ("a.py", "k = ec.generate_private_key(ec.SECP384R1())", "ECDSA-P-384"),
    ("a.py", "k = ec.generate_private_key(ec.SECP521R1())", "ECDSA-P-521"),
    ("a.js", "crypto.generateKeyPairSync('ec', { namedCurve: 'prime256v1' })", "ECDSA-P-256"),
    ("a.go", "priv, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)", "ECDSA-P-256"),
    ("a.py", "signer = ECDSA(hashes.SHA256())", "ECDSA-P-256"),
    ("a.py", "k = ed25519.Ed25519PrivateKey.generate()", "EdDSA-Ed25519"),
    ("a.py", "x = x25519.X25519PrivateKey.generate()", "X25519"),
    ("a.js", "const ecdh = crypto.createECDH('prime256v1')", "ECDH-P-256"),
    ("a.js", "const ecdh = crypto.createECDH('secp384r1')", "ECDH-P-384"),
    ("a.js", "const dh = crypto.createDiffieHellman(2048)", "DH"),
    ("a.py", "params = dh.generate_parameters(generator=2, key_size=2048)", "DH"),
    ("a.py", "k = dsa.generate_private_key(key_size=2048)", "DSA"),
    ("a.py", "key = AESGCM.generate_key(bit_length=128)", "AES-128"),
    ("a.py", "key = AESGCM.generate_key(bit_length=256)", "AES-256"),
    ("a.js", "crypto.createCipheriv('aes-128-gcm', key, iv)", "AES-128"),
    ("a.js", "crypto.createCipheriv('aes-256-gcm', key, iv)", "AES-256"),
    ("a.yaml", "cipher: AES_256", "AES-256"),
    ("a.py", "c = ChaCha20Poly1305(key)", "ChaCha20-Poly1305"),
    ("a.py", "h = hashlib.md5(data).hexdigest()", "MD5"),
    ("a.js", "crypto.createHash('md5')", "MD5"),
    ("a.py", "h = hashlib.sha1(data)", "SHA-1"),
    ("a.js", "crypto.createHash('sha1')", "SHA-1"),
    ("a.py", "c = DES.new(key, DES.MODE_ECB)", "DES"),
    ("a.java", 'Cipher.getInstance("DESede")  // TripleDES', "3DES"),
    ("a.py", "c = ARC4.new(key)", "RC4"),
    ("a.py", "from kyber_py.ml_kem import ML_KEM_768", "ML-KEM"),
    ("a.py", "from dilithium_py.ml_dsa import ML_DSA_65", "ML-DSA"),
    ("a.go", "sig := sphincs.Sign(sk, msg) // SPHINCS+", "SLH-DSA"),
    ("a.toml", 'algorithm = "ML-KEM-768"', "ML-KEM"),
    ("a.properties", "jwt.algorithm=RS512", "RSA-2048"),
    ("a.kt", 'val kpg = KeyPairGenerator.getInstance("RSA")', "RSA-2048"),
    ("a.rs", "let key = RsaPrivateKey::new(&mut rng, 2048) // RSA_PSS", "RSA-2048"),
]

NEGATIVE = [
    # (filename, source line, algorithm that must NOT be reported)
    ("a.py", "description = 'DESCRIPTION of the API'", "DES"),
    ("a.py", "x = DESCENDING", "DES"),
    ("a.py", "verse = 'rsamples are fine'", "RSA-2048"),
    ("a.py", "md = markdown(text)", "MD5"),
    ("a.py", "sha256(data)", "SHA-1"),
    ("a.py", "hashlib.sha256(data)", "SHA-1"),
    ("a.js", "const ecdh = crypto.createECDH('prime256v1')", "ECDSA-P-256"),  # key exchange, not signatures
    ("a.py", "AES_BLOCK = 16", "AES-128"),
    ("a.py", "decode_es(document)", "ECDSA-P-256"),
    ("a.md", "We use RSA-2048 everywhere", "RSA-2048"),        # markdown is not scanned
    ("a.png", "rsa.generate_private_key(key_size=2048)", "RSA-2048"),  # not a source file
]


def scan_one(tmp_path, filename, line):
    (tmp_path / filename).write_text(line + "\n", encoding="utf8")
    return {a["algorithm"] for a in scanner.scan_code(str(tmp_path))["assets"]}


@pytest.mark.parametrize("filename,line,expected", POSITIVE, ids=[f"{e}:{f}:{i}" for i, (f, _, e) in enumerate(POSITIVE)])
def test_detects(tmp_path, filename, line, expected):
    assert expected in scan_one(tmp_path, filename, line)


@pytest.mark.parametrize("filename,line,absent", NEGATIVE, ids=[f"not-{a}:{i}" for i, (_, _, a) in enumerate(NEGATIVE)])
def test_does_not_misfire(tmp_path, filename, line, absent):
    assert absent not in scan_one(tmp_path, filename, line)


def test_assumed_sizes_are_flagged(tmp_path):
    (tmp_path / "a.py").write_text('jwt.encode(c, k, algorithm="RS256")\n', encoding="utf8")
    finding = scanner.scan_code(str(tmp_path))["assets"][0]
    assert "assumed 2048" in finding["detail"]


def test_location_has_file_and_line(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "x.py").write_text("\n\nh = hashlib.md5(b'')\n", encoding="utf8")
    finding = scanner.scan_code(str(tmp_path))["assets"][0]
    assert finding["location"] == "sub/x.py:3"
