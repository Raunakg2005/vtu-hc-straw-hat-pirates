"""Post-quantum migration: ML-KEM-768 and ML-DSA-65 behave as the standards require."""

import pytest
from dilithium_py.ml_dsa import ML_DSA_65
from hypothesis import given, settings
from hypothesis import strategies as st
from kyber_py.ml_kem import ML_KEM_768

from qday.migrate.pqc import hybrid_key_exchange, signature_comparison


@pytest.fixture(scope="module")
def kem_keys():
    return ML_KEM_768.keygen()


@pytest.fixture(scope="module")
def dsa_keys():
    return ML_DSA_65.keygen()


@pytest.mark.parametrize("trial", range(10))
def test_ml_kem_roundtrip(kem_keys, trial):
    ek, dk = kem_keys
    key, ct = ML_KEM_768.encaps(ek)
    assert ML_KEM_768.decaps(dk, ct) == key and len(key) == 32


@pytest.mark.parametrize("position", [0, 1, 100, 500, 1087])
def test_ml_kem_tampered_ciphertext_gives_a_different_key(kem_keys, position):
    """Implicit rejection: a modified ciphertext decapsulates to an unrelated key, never the real one."""
    ek, dk = kem_keys
    key, ct = ML_KEM_768.encaps(ek)
    bad = bytearray(ct)
    bad[position] ^= 0x01
    assert ML_KEM_768.decaps(dk, bytes(bad)) != key


def test_ml_kem_wrong_private_key(kem_keys):
    ek, _ = kem_keys
    _, other_dk = ML_KEM_768.keygen()
    key, ct = ML_KEM_768.encaps(ek)
    assert ML_KEM_768.decaps(other_dk, ct) != key


def test_ml_kem_sizes_match_fips_203(kem_keys):
    ek, dk = kem_keys
    _, ct = ML_KEM_768.encaps(ek)
    assert (len(ek), len(dk), len(ct)) == (1184, 2400, 1088)


@given(st.binary(min_size=0, max_size=256))
@settings(max_examples=15, deadline=None)
def test_ml_dsa_signs_any_message(dsa_keys, message):
    pk, sk = dsa_keys
    assert ML_DSA_65.verify(pk, message, ML_DSA_65.sign(sk, message))


@pytest.mark.parametrize("position", [0, 7, 100, 1000, 2000, 3308])
def test_ml_dsa_tampered_signature_rejected(dsa_keys, position):
    pk, sk = dsa_keys
    sig = bytearray(ML_DSA_65.sign(sk, b"carbon credit #42"))
    sig[position] ^= 0x80
    assert not ML_DSA_65.verify(pk, b"carbon credit #42", bytes(sig))


@pytest.mark.parametrize("message,altered", [(b"pay 100", b"pay 900"), (b"", b"\x00"), (b"abc", b"abcd")])
def test_ml_dsa_altered_message_rejected(dsa_keys, message, altered):
    pk, sk = dsa_keys
    assert not ML_DSA_65.verify(pk, altered, ML_DSA_65.sign(sk, message))


def test_ml_dsa_wrong_public_key_rejected(dsa_keys):
    _, sk = dsa_keys
    other_pk, _ = ML_DSA_65.keygen()
    assert not ML_DSA_65.verify(other_pk, b"m", ML_DSA_65.sign(sk, b"m"))


def test_ml_dsa_sizes_match_fips_204(dsa_keys):
    pk, sk = dsa_keys
    assert (len(pk), len(ML_DSA_65.sign(sk, b"x"))) == (1952, 3309)


@pytest.mark.parametrize("trial", range(5))
def test_hybrid_handshake(trial):
    h = hybrid_key_exchange()
    assert h["keys_match"] and h["message_roundtrip"]
    assert h["client_to_server_bytes"] == 1088 + 32 and h["server_to_client_bytes"] == 1184 + 32


def test_signature_comparison_table():
    rows = {r["algorithm"]: r for r in signature_comparison()}
    assert set(rows) == {"RSA-2048", "ECDSA P-256", "ML-DSA-65"}
    assert rows["ML-DSA-65"]["quantum_safe"] and not rows["RSA-2048"]["quantum_safe"]
    assert rows["ML-DSA-65"]["tampered_rejected"]
