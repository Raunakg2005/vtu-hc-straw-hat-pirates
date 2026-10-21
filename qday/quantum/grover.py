"""Grover key search against a toy block cipher.

Toy cipher on n-bit blocks with an n-bit key: E_k(p) = S(p XOR k), where S is a nonlinear
n-bit S-box (n = 4 uses the S-box of the PRESENT lightweight cipher; n = 3 uses a small
toy S-box so the circuit is shallow enough for current hardware). Given one known
plaintext/ciphertext pair (p, c), the oracle evaluates the cipher on a superposition of all
keys and flips the phase of keys with E_k(p) = c. It only uses the public pair (p, c),
never the secret key.

Classical brute force needs up to 2^n trials; Grover needs about (pi/4) * sqrt(2^n) oracle
calls. For a real n-bit key this halves the effective security (2^n -> 2^(n/2)), which is
why AES-128 is considered weakened and AES-256 recommended.
"""

from math import asin, floor, pi, sin, sqrt

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.circuit.library import UnitaryGate

SBOXES = {
    3: [3, 6, 0, 5, 7, 1, 4, 2],  # toy nonlinear 3-bit permutation
    4: [0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0xA, 0xD, 0x3, 0xE, 0xF, 0x8, 0x4, 0x7, 0x1, 0x2],  # PRESENT
}


def toy_encrypt(plaintext: int, key: int, n_bits: int = 4) -> int:
    return SBOXES[n_bits][plaintext ^ key]


def _sbox_gate(n_bits: int, inverse: bool = False) -> UnitaryGate:
    dim = 2**n_bits
    m = np.zeros((dim, dim))
    for x in range(dim):
        m[SBOXES[n_bits][x], x] = 1
    return UnitaryGate(m.T if inverse else m, label="S⁻¹" if inverse else "S")


def _phase_flip_all_ones(qc: QuantumCircuit, n_bits: int) -> None:
    qc.h(n_bits - 1)
    qc.mcx(list(range(n_bits - 1)), n_bits - 1)
    qc.h(n_bits - 1)


def oracle(plaintext: int, ciphertext: int, n_bits: int = 4) -> QuantumCircuit:
    """Phase-flip every key k with S(p XOR k) == c."""
    qc = QuantumCircuit(n_bits, name="oracle")
    flip_p = [i for i in range(n_bits) if (plaintext >> i) & 1]
    flip_c = [i for i in range(n_bits) if not (ciphertext >> i) & 1]
    if flip_p:
        qc.x(flip_p)  # k -> k XOR p
    qc.append(_sbox_gate(n_bits), range(n_bits))  # -> S(k XOR p)
    if flip_c:
        qc.x(flip_c)  # target value c -> |1...1>
    _phase_flip_all_ones(qc, n_bits)
    if flip_c:
        qc.x(flip_c)
    qc.append(_sbox_gate(n_bits, inverse=True), range(n_bits))
    if flip_p:
        qc.x(flip_p)
    return qc


def diffuser(n_bits: int = 4) -> QuantumCircuit:
    qc = QuantumCircuit(n_bits, name="diffuser")
    qc.h(range(n_bits))
    qc.x(range(n_bits))
    _phase_flip_all_ones(qc, n_bits)
    qc.x(range(n_bits))
    qc.h(range(n_bits))
    return qc


def optimal_iterations(n_bits: int = 4, n_marked: int = 1) -> int:
    return floor(pi / 4 * sqrt(2**n_bits / n_marked))


def theoretical_success(iterations: int, n_bits: int = 4) -> float:
    theta = asin(sqrt(1 / 2**n_bits))
    return sin((2 * iterations + 1) * theta) ** 2


def grover_key_search_circuit(plaintext: int, ciphertext: int, iterations: int = None,
                              n_bits: int = 4) -> QuantumCircuit:
    iterations = optimal_iterations(n_bits) if iterations is None else iterations
    key = QuantumRegister(n_bits, "key")
    meas = ClassicalRegister(n_bits, "meas")
    qc = QuantumCircuit(key, meas, name=f"grover_n{n_bits}_p{plaintext}_c{ciphertext}_it{iterations}")
    qc.h(key)
    ora, dif = oracle(plaintext, ciphertext, n_bits).to_gate(), diffuser(n_bits).to_gate()
    for _ in range(iterations):
        qc.append(ora, key)
        qc.append(dif, key)
    qc.measure(key, meas)
    return qc


def parse_name(name: str) -> dict:
    """Recover (n_bits, plaintext, ciphertext, iterations) from a circuit name."""
    import re

    m = re.fullmatch(r"grover_n(\d+)_p(\d+)_c(\d+)_it(\d+)", name)
    if not m:
        raise ValueError(f"not a Grover circuit name: {name}")
    n, p, c, it = map(int, m.groups())
    return {"n_bits": n, "plaintext": p, "ciphertext": c, "iterations": it}


def analyse_counts(counts: dict, plaintext: int, ciphertext: int, iterations: int,
                   n_bits: int = 4) -> dict:
    total = sum(counts.values())
    candidates = sorted(((int(b, 2), s) for b, s in counts.items()), key=lambda kv: -kv[1])
    best = candidates[0][0]
    valid = [k for k in range(2**n_bits) if toy_encrypt(plaintext, k, n_bits) == ciphertext]
    hit = sum(s for k, s in candidates if k in valid)
    return {
        "n_bits": n_bits,
        "plaintext": plaintext,
        "ciphertext": ciphertext,
        "iterations": iterations,
        "shots": total,
        "recovered_key": best,
        "key_is_correct": toy_encrypt(plaintext, best, n_bits) == ciphertext,
        "success_probability": hit / total if total else 0.0,
        "theoretical_success": theoretical_success(iterations, n_bits),
        "random_guess_baseline": 1 / 2**n_bits,
        "classical_worst_case_trials": 2**n_bits,
        "distribution": {k: s / total for k, s in candidates},
    }
