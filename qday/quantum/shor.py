"""Shor's algorithm: quantum order finding with real modular-multiplication circuits.

Order finding estimates the period r of f(x) = a^x mod N with quantum phase estimation.
Counting qubit j controls "multiply by a^(2^j) mod N" on the work register. The constants
a^(2^j) mod N are computed classically by repeated squaring (polynomial time, as in every
Shor implementation); the multiplier circuit itself is synthesised generically for any
constant coprime to N, so the circuit never encodes the answer r.

* N = 15: each multiplier is a bit rotation, optionally followed by bitwise NOT, because
  every unit mod 15 is +/- 2^k and 15 - x = NOT x on 4 bits. Small enough for hardware.
* Any other N (e.g. 21): the multiplier is the permutation unitary x -> c*x mod N
  (simulator scale).
"""

from fractions import Fraction
from math import gcd

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.circuit.library import QFTGate, UnitaryGate


def _rotate_left(qc: QuantumCircuit, qubits, k: int) -> None:
    """Cyclic left shift of a little-endian register by k bits (x -> 2^k x mod 2^n - 1).

    Bit i moves to position (i + k) mod n; each cycle of that permutation costs len - 1 swaps.
    """
    n = len(qubits)
    k %= n
    seen = set()
    for start in range(n):
        if start in seen:
            continue
        cycle, i = [], start
        while i not in seen:
            seen.add(i)
            cycle.append(i)
            i = (i + k) % n
        # moving each bit forward along the cycle = swapping from the end backwards
        for j in range(len(cycle) - 1, 0, -1):
            qc.swap(qubits[cycle[j]], qubits[cycle[j - 1]])


def _multiplier_mod15(c: int) -> QuantumCircuit:
    qc = QuantumCircuit(4, name=f"x{c} mod 15")
    q = list(range(4))
    for k in range(4):
        if pow(2, k, 15) == c:
            _rotate_left(qc, q, k)
            return qc
        if (15 - pow(2, k, 15)) % 15 == c:
            _rotate_left(qc, q, k)
            qc.x(q)
            return qc
    raise ValueError(f"{c} is not a unit mod 15")


def _multiplier_permutation(c: int, N: int, n_work: int) -> UnitaryGate:
    dim = 2**n_work
    matrix = np.zeros((dim, dim))
    for x in range(dim):
        y = (c * x) % N if x < N else x
        matrix[y, x] = 1
    return UnitaryGate(matrix, label=f"x{c} mod {N}")


def modular_multiplier(c: int, N: int):
    """Gate (or circuit) for |x> -> |c*x mod N> on the work register (valid for 0 < x < N)."""
    if gcd(c, N) != 1:
        raise ValueError(f"c={c} must be coprime to N={N}")
    if N == 15:
        return _multiplier_mod15(c % 15)
    return _multiplier_permutation(c % N, N, N.bit_length())


def _controlled_multiplier(c: int, N: int):
    op = modular_multiplier(c, N)
    gate = op.to_gate() if isinstance(op, QuantumCircuit) else op
    return gate.control(1)


def order_finding_circuit(a: int, N: int, n_count: int = 4) -> QuantumCircuit:
    """Phase-estimation circuit whose measured register y satisfies y/2^n ~ s/r."""
    if gcd(a, N) != 1:
        raise ValueError(f"a={a} shares a factor with N={N}; no quantum step needed")
    n_work = N.bit_length()
    count = QuantumRegister(n_count, "count")
    work = QuantumRegister(n_work, "work")
    meas = ClassicalRegister(n_count, "meas")
    qc = QuantumCircuit(count, work, meas, name=f"shor_N{N}_a{a}")
    qc.h(count)
    qc.x(work[0])  # work register starts in |1>
    for j in range(n_count):
        c = pow(a, 2**j, N)  # classical repeated squaring
        if c == 1:
            continue  # controlled identity
        qc.append(_controlled_multiplier(c, N), [count[j], *work])
    qc.append(QFTGate(n_count).inverse(), count)
    qc.measure(count, meas)
    return qc


def order_from_measurement(y: int, n_count: int, a: int, N: int):
    """Continued-fraction step: the smallest r with a^r = 1 mod N consistent with y."""
    if y == 0:
        return None
    frac = Fraction(y, 2**n_count).limit_denominator(N)
    r = frac.denominator
    for multiple in range(1, N // max(r, 1) + 1):  # recover r when s and r share a factor
        if pow(a, r * multiple, N) == 1:
            return r * multiple
    return None


def factors_from_order(a: int, r, N: int):
    """Classical post-processing: gcd(a^(r/2) +/- 1, N) when r is even and a^(r/2) != -1."""
    if r is None or r % 2:
        return None
    half = pow(a, r // 2, N)
    if half == N - 1:
        return None
    p, q = gcd(half - 1, N), gcd(half + 1, N)
    for f in (p, q):
        if 1 < f < N:
            return tuple(sorted((f, N // f)))
    return None


def analyse_counts(counts: dict, a: int, N: int, n_count: int) -> dict:
    """Turn measurement counts into factoring statistics."""
    total = sum(counts.values())
    per_outcome, success_shots, orders, factors = [], 0, {}, None
    for bitstring, shots in sorted(counts.items(), key=lambda kv: -kv[1]):
        y = int(bitstring, 2)
        r = order_from_measurement(y, n_count, a, N)
        f = factors_from_order(a, r, N)
        per_outcome.append({"y": y, "phase": y / 2**n_count, "shots": shots, "order": r, "factors": f})
        if r:
            orders[r] = orders.get(r, 0) + shots
        if f:
            success_shots += shots
            factors = factors or f
    true_order = next(r for r in range(1, N) if pow(a, r, N) == 1)
    # what pure noise (uniformly random y) would score: the bar real hardware must beat
    noise_hits = sum(
        1 for y in range(2**n_count) if factors_from_order(a, order_from_measurement(y, n_count, a, N), N)
    )
    return {
        "random_noise_baseline": noise_hits / 2**n_count,
        "a": a,
        "N": N,
        "n_count": n_count,
        "shots": total,
        "true_order": true_order,
        "most_likely_order": max(orders, key=orders.get) if orders else None,
        "factors": factors,
        "success_probability": success_shots / total if total else 0.0,
        "outcomes": per_outcome,
    }
