"""Exhaustive checks of the Grover attack and the toy cipher, using exact statevector probabilities."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from qiskit.quantum_info import Operator, Statevector

from qday.quantum import grover


def exact_success(p, secret, iterations, n_bits):
    c = grover.toy_encrypt(p, secret, n_bits)
    qc = grover.grover_key_search_circuit(p, c, iterations, n_bits).remove_final_measurements(inplace=False)
    probs = Statevector(qc).probabilities_dict()
    return probs.get(format(secret, f"0{n_bits}b"), 0.0)


@pytest.mark.parametrize("p", range(8))
@pytest.mark.parametrize("secret", range(8))
def test_3bit_every_plaintext_and_key(p, secret):
    assert exact_success(p, secret, 2, 3) == pytest.approx(grover.theoretical_success(2, 3), abs=1e-9)


@pytest.mark.parametrize("secret", range(16))
def test_4bit_every_key(secret):
    assert exact_success(5, secret, 3, 4) == pytest.approx(grover.theoretical_success(3, 4), abs=1e-9)


@pytest.mark.parametrize("p", range(16))
def test_4bit_every_plaintext(p):
    assert exact_success(p, 9, 3, 4) == pytest.approx(grover.theoretical_success(3, 4), abs=1e-9)


@pytest.mark.parametrize("n_bits", [3, 4])
@pytest.mark.parametrize("iterations", range(7))
def test_success_follows_sin_squared(n_bits, iterations):
    assert exact_success(3, 2, iterations, n_bits) == pytest.approx(
        grover.theoretical_success(iterations, n_bits), abs=1e-9)


@pytest.mark.parametrize("n_bits,key", [(3, k) for k in range(8)] + [(4, k) for k in range(16)])
def test_toy_cipher_is_a_permutation_for_every_key(n_bits, key):
    images = {grover.toy_encrypt(p, key, n_bits) for p in range(2**n_bits)}
    assert images == set(range(2**n_bits))


@pytest.mark.parametrize("n_bits", [3, 4])
def test_sbox_is_nonlinear(n_bits):
    """S(x ^ y) != S(x) ^ S(y) for some pair: the cipher is not just XOR."""
    s = grover.SBOXES[n_bits]
    assert any(s[x ^ y] != s[x] ^ s[y] ^ s[0] for x in range(2**n_bits) for y in range(2**n_bits))


@pytest.mark.parametrize("n_bits,secret", [(3, k) for k in range(8)] + [(4, k) for k in range(16)])
def test_oracle_flips_exactly_the_secret(n_bits, secret):
    p = 5
    c = grover.toy_encrypt(p, secret, n_bits)
    U = Operator(grover.oracle(p, c, n_bits)).data
    assert np.allclose(U, np.diag(np.diag(U)), atol=1e-9)  # diagonal: only phases
    expected = np.ones(2**n_bits)
    expected[secret] = -1
    assert np.allclose(np.real(np.diag(U)), expected, atol=1e-9)


@pytest.mark.parametrize("n_bits", [3, 4])
def test_diffuser_is_inversion_about_the_mean(n_bits):
    dim = 2**n_bits
    expected = 2 * np.full((dim, dim), 1 / dim) - np.eye(dim)
    U = Operator(grover.diffuser(n_bits)).data
    phase = U[0, 0] / expected[0, 0]
    assert np.allclose(U, phase * expected, atol=1e-9)


@pytest.mark.parametrize("n_bits,expected", [(3, 2), (4, 3), (6, 6), (8, 12)])
def test_optimal_iterations(n_bits, expected):
    assert grover.optimal_iterations(n_bits) == expected


@given(st.integers(3, 4), st.integers(0, 15), st.integers(0, 15), st.integers(0, 9))
def test_name_roundtrip(n_bits, p, c, it):
    name = grover.grover_key_search_circuit(p % 2**n_bits, c % 2**n_bits, it, n_bits).name
    assert grover.parse_name(name) == {"n_bits": n_bits, "plaintext": p % 2**n_bits,
                                       "ciphertext": c % 2**n_bits, "iterations": it}


@pytest.mark.parametrize("bad", ["grover_n3", "shor_N15_a7", "grover_nX_p1_c2_it3", ""])
def test_parse_name_rejects_garbage(bad):
    with pytest.raises(ValueError):
        grover.parse_name(bad)


@pytest.mark.parametrize("secret", range(8))
def test_analysis_identifies_correct_key(secret):
    c = grover.toy_encrypt(5, secret, 3)
    counts = {format(k, "03b"): (900 if k == secret else 10) for k in range(8)}
    r = grover.analyse_counts(counts, 5, c, 2, 3)
    assert r["recovered_key"] == secret and r["key_is_correct"]
