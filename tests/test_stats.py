import pytest

from qday.quantum.stats import p_value_above_baseline, summarise, tvd, wilson_interval


def test_wilson_contains_rate_and_is_bounded():
    lo, hi = wilson_interval(680, 1000)
    assert 0 <= lo < 0.68 < hi <= 1
    assert hi - lo < 0.06  # ~±3% at n = 1000


def test_wilson_edge_cases():
    assert wilson_interval(0, 100)[0] == 0.0
    assert wilson_interval(100, 100)[1] == 1.0
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_binomial_p_value_separates_signal_from_noise():
    assert p_value_above_baseline(2720, 4000, 0.375) < 1e-100  # hardware Shor-like signal
    assert p_value_above_baseline(1500, 4000, 0.375) > 0.4     # exactly the noise rate


def test_tvd():
    assert tvd({"a": 1.0}, {"a": 1.0}) == 0
    assert tvd({"a": 1.0}, {"b": 1.0}) == 1
    assert tvd({"a": .5, "b": .5}, {"a": 1.0}) == pytest.approx(0.5)


def test_summarise_flags_significance():
    assert summarise(2180, 4000, 0.125)["significant"]
    assert not summarise(520, 4000, 0.125)["significant"]
