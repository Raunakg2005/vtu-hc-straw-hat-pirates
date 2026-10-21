"""Post-quantum migration demo: ML-KEM-768 (FIPS 203), ML-DSA-65 (FIPS 204), and a hybrid
X25519 + ML-KEM-768 key exchange, compared side by side with the classical algorithms.

The hybrid combiner concatenates the ML-KEM and X25519 shared secrets (ML-KEM first, as in
the X25519MLKEM768 TLS group) and derives the session key with HKDF-SHA256, so the session
stays secret as long as EITHER component is unbroken.
"""

import os
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa, x25519
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from dilithium_py.ml_dsa import ML_DSA_65
from kyber_py.ml_kem import ML_KEM_768


def _timed(fn, *args):
    t0 = time.perf_counter()
    out = fn(*args)
    return out, (time.perf_counter() - t0) * 1000


def hybrid_key_exchange() -> dict:
    """Client/server hybrid handshake; returns sizes, timings and whether both sides agree."""
    # server: long-term-for-this-session keys
    (ek, dk), t_kg = _timed(ML_KEM_768.keygen)
    srv_x = x25519.X25519PrivateKey.generate()
    # client: encapsulate to ML-KEM key + X25519 exchange
    (k_mlkem_c, ct), t_enc = _timed(ML_KEM_768.encaps, ek)
    cli_x = x25519.X25519PrivateKey.generate()
    k_x_c = cli_x.exchange(srv_x.public_key())
    # server: decapsulate + X25519
    k_mlkem_s, t_dec = _timed(ML_KEM_768.decaps, dk, ct)
    k_x_s = srv_x.exchange(cli_x.public_key())

    def derive(k_mlkem, k_x):
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                    info=b"qday hybrid X25519MLKEM768 demo").derive(k_mlkem + k_x)

    client_key, server_key = derive(k_mlkem_c, k_x_c), derive(k_mlkem_s, k_x_s)
    nonce = os.urandom(12)
    message = b"Transfer INR 50,000 to account 1234 - quantum-safe session"
    ciphertext = AESGCM(client_key).encrypt(nonce, message, None)
    decrypted = AESGCM(server_key).decrypt(nonce, ciphertext, None)
    x_pub = srv_x.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {
        "keys_match": client_key == server_key,
        "message_roundtrip": decrypted == message,
        "client_to_server_bytes": len(ct) + 32,
        "server_to_client_bytes": len(ek) + len(x_pub),
        "ml_kem_ms": {"keygen": t_kg, "encaps": t_enc, "decaps": t_dec},
        "session_key_bits": len(client_key) * 8,
        "aes_gcm_ciphertext_bytes": len(ciphertext),
    }


def signature_comparison(message: bytes = b"carbon-credit #0042 retired by Quantyxio") -> list:
    """Sign and verify the same message with RSA-2048, ECDSA P-256 and ML-DSA-65."""
    rows = []

    rsa_key, t_kg = _timed(rsa.generate_private_key, 65537, 2048)
    pss = rsa_padding.PSS(mgf=rsa_padding.MGF1(hashes.SHA256()), salt_length=rsa_padding.PSS.MAX_LENGTH)
    sig, t_s = _timed(rsa_key.sign, message, pss, hashes.SHA256())
    t0 = time.perf_counter()
    rsa_key.public_key().verify(sig, message, pss, hashes.SHA256())
    rows.append({"algorithm": "RSA-2048", "quantum_safe": False, "public_key_bytes": 256 + 3,
                 "signature_bytes": len(sig), "sign_ms": t_s, "verify_ms": (time.perf_counter() - t0) * 1000,
                 "keygen_ms": t_kg})

    ec_key, t_kg = _timed(ec.generate_private_key, ec.SECP256R1())
    sig, t_s = _timed(ec_key.sign, message, ec.ECDSA(hashes.SHA256()))
    t0 = time.perf_counter()
    ec_key.public_key().verify(sig, message, ec.ECDSA(hashes.SHA256()))
    rows.append({"algorithm": "ECDSA P-256", "quantum_safe": False, "public_key_bytes": 65,
                 "signature_bytes": len(sig), "sign_ms": t_s, "verify_ms": (time.perf_counter() - t0) * 1000,
                 "keygen_ms": t_kg})

    (pk, sk), t_kg = _timed(ML_DSA_65.keygen)
    sig, t_s = _timed(ML_DSA_65.sign, sk, message)
    ok, t_v = _timed(ML_DSA_65.verify, pk, message, sig)
    tampered_rejected = not ML_DSA_65.verify(pk, message + b"!", sig)
    rows.append({"algorithm": "ML-DSA-65", "quantum_safe": True, "public_key_bytes": len(pk),
                 "signature_bytes": len(sig), "sign_ms": t_s, "verify_ms": t_v, "keygen_ms": t_kg,
                 "verified": ok, "tampered_rejected": tampered_rejected})
    return rows
