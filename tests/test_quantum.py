from math import gcd

import pytest
from qiskit import transpile
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator

from qday.quantum import grover, shor

SIM = AerSimulator()


def _counts(qc, shots=3000, seed=11):
    return SIM.run(transpile(qc, SIM), shots=shots, seed_simulator=seed).result().get_counts()


@pytest.mark.parametrize("N", [15, 21])
def test_modular_multiplier_is_correct_for_every_input(N):
    n = N.bit_length()
    for c in (c for c in range(2, N) if gcd(c, N) == 1):
        op = shor.modular_multiplier(c, N)
        for x in range(1, N):
            sv = Statevector.from_int(x, 2**n).evolve(op)
            probs = sv.probabilities_dict()
            assert int(max(probs, key=probs.get), 2) == (c * x) % N


@pytest.mark.parametrize("a", [2, 7, 8, 11, 13])
def test_shor_factors_15(a):
    r = shor.analyse_counts(_counts(shor.order_finding_circuit(a, 15, 4)), a, 15, 4)
    assert r["factors"] == (3, 5)
    assert r["most_likely_order"] == r["true_order"]
    assert r["success_probability"] > r["random_noise_baseline"]


def test_shor_factors_21():
    r = shor.analyse_counts(_counts(shor.order_finding_circuit(2, 21, 6)), 2, 21, 6)
    assert r["factors"] == (3, 7)
    assert r["true_order"] == 6


def test_shor_reports_trivial_case():
    # 5^3 = -1 mod 21: the period is found but yields no factor (retry with another a)
    r = shor.analyse_counts(_counts(shor.order_finding_circuit(5, 21, 6)), 5, 21, 6)
    assert r["most_likely_order"] == 6 and r["factors"] is None


def test_shor_rejects_non_coprime_base():
    with pytest.raises(ValueError):
        shor.order_finding_circuit(5, 15)


@pytest.mark.parametrize("n_bits", [3, 4])
def test_grover_recovers_every_secret_key(n_bits):
    p = 5
    for secret in range(2**n_bits):
        c = grover.toy_encrypt(p, secret, n_bits)
        qc = grover.grover_key_search_circuit(p, c, None, n_bits)
        r = grover.analyse_counts(_counts(qc, 1500), p, c, grover.optimal_iterations(n_bits), n_bits)
        assert r["recovered_key"] == secret


def test_grover_matches_theory():
    p, c = 10, grover.toy_encrypt(10, 9)
    for it in range(5):
        r = grover.analyse_counts(_counts(grover.grover_key_search_circuit(p, c, it), 8000), p, c, it)
        assert abs(r["success_probability"] - r["theoretical_success"]) < 0.03


def test_grover_name_roundtrip():
    qc = grover.grover_key_search_circuit(5, 3, 2, 3)
    assert grover.parse_name(qc.name) == {"n_bits": 3, "plaintext": 5, "ciphertext": 3, "iterations": 2}
