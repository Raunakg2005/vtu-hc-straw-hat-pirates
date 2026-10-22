"""The strict criteria must accept good data and reject noise — checked on synthetic counts."""

import numpy as np

from qday.quantum import validation as v

IDEAL_SHOR = {"000": .25, "010": .25, "100": .25, "110": .25}  # order 4, 3 counting bits
IDEAL_GROVER = {format(k, "03b"): (.945 if k == 6 else .055 / 7) for k in range(8)}


def sample(probs: dict, shots=4000, seed=0):
    rng = np.random.default_rng(seed)
    keys = list(probs)
    draws = rng.multinomial(shots, [probs[k] for k in keys])
    return {k: int(n) for k, n in zip(keys, draws) if n}


def mix(ideal: dict, w_signal: float, n_bits=3):
    keys = [format(i, f"0{n_bits}b") for i in range(2**n_bits)]
    return {k: w_signal * ideal.get(k, 0) + (1 - w_signal) / len(keys) for k in keys}


def test_half_signal_bar_is_between_noise_and_ideal():
    bar = v.half_signal_fidelity(IDEAL_SHOR, 3)
    assert 0.5 < bar < 1.0


def test_good_shor_passes_and_noise_fails():
    good = sample(mix(IDEAL_SHOR, 0.8))
    noise = sample(mix(IDEAL_SHOR, 0.0))
    assert v.shor_dominance(good, IDEAL_SHOR)["pass"]
    assert v.fidelity(good, IDEAL_SHOR, 3)["pass"]
    assert not v.fidelity(noise, IDEAL_SHOR, 3)["pass"]


def test_grover_dominance_requires_secret_and_margin():
    good = sample(mix(IDEAL_GROVER, 0.6))
    assert v.grover_dominance(good, 6, 3)["pass"]
    assert not v.grover_dominance(good, 5, 3)["pass"]          # wrong secret
    weak = sample(mix(IDEAL_GROVER, 0.08))                       # barely above noise
    assert not v.grover_dominance(weak, 6, 3)["pass"]


def test_signal_uses_bonferroni():
    assert v.signal(600, 4000, 0.125, m_tests=50)["pass"]
    assert not v.signal(540, 4000, 0.125, m_tests=50)["pass"]   # 13.5% vs 12.5%: not enough


def test_sweep_fingerprint():
    theory = [.125, .781, .945, .330, .012]
    damped = [round(.6 * x + .4 / 8, 3) for x in theory]        # 60% signal + 40% depolarizing noise
    flat = [.13, .14, .12, .13, .12]                             # pure noise
    assert v.sweep_fingerprint(damped, 4000, theory)["pass"]
    assert not v.sweep_fingerprint(flat, 4000, theory)["pass"]


def test_repeatability():
    a = sample(mix(IDEAL_SHOR, .8), seed=1)
    b = sample(mix(IDEAL_SHOR, .8), seed=2)
    c = sample(mix(IDEAL_SHOR, .2), seed=3)
    assert v.repeatability(a, b)["pass"]
    assert not v.repeatability(a, c)["pass"]
