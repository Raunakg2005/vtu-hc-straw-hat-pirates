"""Property-based tests for the statistics behind every hardware verdict."""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from qday.quantum import validation as v
from qday.quantum.stats import normalise, p_value_above_baseline, summarise, tvd, wilson_interval

counts_st = st.dictionaries(st.sampled_from([format(i, "03b") for i in range(8)]), st.integers(1, 5000),
                            min_size=1, max_size=8)


@given(st.integers(0, 10_000), st.integers(1, 10_000))
def test_wilson_bounds(k, n):
    assume(k <= n)
    lo, hi = wilson_interval(k, n)
    assert 0 <= lo <= k / n <= hi <= 1


@given(st.integers(1, 500), st.integers(2, 50))
def test_wilson_narrows_with_more_shots(k, factor):
    n = 1000
    assume(k <= n)
    lo1, hi1 = wilson_interval(k, n)
    lo2, hi2 = wilson_interval(k * factor, n * factor)
    assert hi2 - lo2 < hi1 - lo1


@given(st.integers(0, 4000), st.floats(0.01, 0.99))
@settings(max_examples=200)
def test_p_value_is_a_probability(k, p0):
    assert 0 <= p_value_above_baseline(k, 4000, p0) <= 1


@given(st.integers(0, 3999), st.floats(0.01, 0.99))
@settings(max_examples=200)
def test_more_successes_never_raise_the_p_value(k, p0):
    assert p_value_above_baseline(k + 1, 4000, p0) <= p_value_above_baseline(k, 4000, p0) + 1e-12


@given(counts_st, counts_st)
def test_tvd_is_a_metric(a, b):
    pa, pb = normalise(a), normalise(b)
    d = tvd(pa, pb)
    assert 0 <= d <= 1 + 1e-12
    assert d == pytest.approx(tvd(pb, pa))
    assert tvd(pa, pa) == pytest.approx(0)


@given(counts_st, counts_st, counts_st)
def test_tvd_triangle_inequality(a, b, c):
    pa, pb, pc = normalise(a), normalise(b), normalise(c)
    assert tvd(pa, pc) <= tvd(pa, pb) + tvd(pb, pc) + 1e-12


@given(counts_st)
def test_normalise_sums_to_one(c):
    assert sum(normalise(c).values()) == pytest.approx(1)


@given(st.integers(0, 4000), st.floats(0.0, 0.9))
def test_summarise_significance_matches_interval(k, p0):
    s = summarise(k, 4000, p0)
    assert s["significant"] == (s["ci95"][0] > p0)


@given(st.integers(1, 200))
def test_bonferroni_never_makes_a_test_easier(m):
    loose = v.signal(560, 4000, 0.125, 1)["pass"]
    strict = v.signal(560, 4000, 0.125, m)["pass"]
    assert loose or not strict


@given(counts_st)
def test_fidelity_bar_is_monotone_in_signal(c):
    ideal = {"000": .5, "100": .5}
    assert v.half_signal_fidelity(ideal, 3) < 1


@pytest.mark.parametrize("ideal", [{"000": 1.0}, {"000": .5, "100": .5}, {"000": .25, "010": .25, "100": .25, "110": .25}])
def test_perfect_data_always_passes_fidelity(ideal):
    counts = {k: round(p * 4000) for k, p in ideal.items()}
    assert v.fidelity(counts, ideal, 3)["pass"]


@pytest.mark.parametrize("ideal", [{"000": 1.0}, {"000": .5, "100": .5}])
def test_uniform_noise_always_fails_fidelity(ideal):
    counts = {format(i, "03b"): 500 for i in range(8)}
    assert not v.fidelity(counts, ideal, 3)["pass"]


def test_identical_runs_are_repeatable():
    a = {"000": 1000, "010": 1000, "100": 1000, "110": 1000}
    assert v.repeatability(a, dict(a))["pass"]
