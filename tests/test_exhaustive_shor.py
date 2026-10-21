"""Exhaustive checks of Shor's order finding using exact statevector probabilities (no sampling)."""

from math import gcd

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from qiskit.quantum_info import Statevector

from qday.quantum import shor

UNITS = {N: [c for c in range(2, N) if gcd(c, N) == 1] for N in (15, 21)}
NON_UNITS = {N: [c for c in range(2, N) if gcd(c, N) != 1] for N in (15, 21)}


def order(a, N):
    return next(r for r in range(1, N) if pow(a, r, N) == 1)


def exact_counts(a, N, n, scale=1_000_000):
    qc = shor.order_finding_circuit(a, N, n).remove_final_measurements(inplace=False)
    probs = Statevector(qc).probabilities_dict(qargs=list(range(n)))
    return {k: round(p * scale) for k, p in probs.items() if round(p * scale) > 0}


# ---------------------------------------------------------------- modular multipliers, one test per constant
@pytest.mark.parametrize("N,c", [(N, c) for N in (15, 21) for c in UNITS[N]])
def test_multiplier_maps_every_input(N, c):
    n = N.bit_length()
    op = shor.modular_multiplier(c, N)
    for x in range(1, N):
        sv = Statevector.from_int(x, 2**n).evolve(op)
        probs = sv.probabilities_dict()
        assert max(probs, key=probs.get) == format((c * x) % N, f"0{n}b")
        assert max(probs.values()) == pytest.approx(1.0)


@pytest.mark.parametrize("N,c", [(N, c) for N in (15, 21) for c in NON_UNITS[N]])
def test_multiplier_rejects_non_units(N, c):
    with pytest.raises(ValueError):
        shor.modular_multiplier(c, N)


@pytest.mark.parametrize("N,a", [(N, a) for N in (15, 21) for a in NON_UNITS[N]])
def test_order_finding_rejects_shared_factor(N, a):
    with pytest.raises(ValueError):
        shor.order_finding_circuit(a, N)


# ---------------------------------------------------------------- order finding, every base
@pytest.mark.parametrize("a", UNITS[15])
@pytest.mark.parametrize("n", [3, 4])
def test_n15_ideal_peaks_are_exact(a, n):
    """For N = 15 every order divides 2^n, so the ideal outcomes are exactly the multiples of 2^n / r."""
    r = order(a, 15)
    counts = exact_counts(a, 15, n)
    expected = {format(k * 2**n // r, f"0{n}b") for k in range(r)}
    assert set(counts) == expected
    for v in counts.values():
        assert v == pytest.approx(1_000_000 / r, rel=1e-4)


@pytest.mark.parametrize("a", UNITS[15])
def test_n15_factoring_outcome_matches_number_theory(a):
    r = order(a, 15)
    res = shor.analyse_counts(exact_counts(a, 15, 3), a, 15, 3)
    trivial = r % 2 == 1 or pow(a, r // 2, 15) == 14
    assert res["true_order"] == r
    assert (res["factors"] is None) == trivial
    if not trivial:
        assert res["factors"] == (3, 5)
        assert res["success_probability"] == pytest.approx(1 - 1 / r, abs=1e-3) or r == 2


@pytest.mark.parametrize("a", UNITS[21])
def test_n21_every_base(a):
    r = order(a, 21)
    res = shor.analyse_counts(exact_counts(a, 21, 6), a, 21, 6)
    trivial = r % 2 == 1 or pow(a, r // 2, 21) == 20
    assert res["most_likely_order"] in (r, None) or r % res["most_likely_order"] == 0
    assert (res["factors"] is None) == trivial
    if not trivial:
        assert res["factors"] == (3, 7)


@pytest.mark.parametrize("N,n", [(15, 3), (15, 4), (21, 5), (21, 6)])
def test_circuit_shape(N, n):
    qc = shor.order_finding_circuit(2, N, n)
    assert qc.num_qubits == n + N.bit_length()
    assert qc.num_clbits == n


@pytest.mark.parametrize("N", [15, 21])
@pytest.mark.parametrize("a_index", range(4))
def test_noise_baseline_is_a_probability(N, a_index):
    a = UNITS[N][a_index]
    res = shor.analyse_counts(exact_counts(a, N, 4), a, N, 4)
    assert 0 <= res["random_noise_baseline"] <= 1


def test_zero_outcome_never_gives_an_order():
    assert shor.order_from_measurement(0, 3, 7, 15) is None


# ---------------------------------------------------------------- classical post-processing properties
SEMIPRIMES = [15, 21, 33, 35, 39, 51, 55, 57, 65, 77, 85, 91]


@given(st.sampled_from(SEMIPRIMES), st.integers(min_value=2, max_value=90))
@settings(max_examples=300, deadline=None)
def test_factors_from_true_order_are_correct(N, a):
    a = a % N
    if a < 2 or gcd(a, N) != 1:
        return
    f = shor.factors_from_order(a, order(a, N), N)
    if f is not None:
        p, q = f
        assert p * q == N and 1 < p < N and 1 < q < N


@given(st.sampled_from(SEMIPRIMES), st.integers(min_value=2, max_value=90), st.integers(1, 6))
@settings(max_examples=300, deadline=None)
def test_order_from_measurement_is_always_a_true_period(N, a, n):
    a = a % N
    if a < 2 or gcd(a, N) != 1:
        return
    for y in range(2**n):
        r = shor.order_from_measurement(y, n, a, N)
        if r is not None:
            assert pow(a, r, N) == 1
