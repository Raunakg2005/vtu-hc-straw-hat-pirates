"""Pre-registered strict pass criteria for hardware runs.

These rules were fixed in code BEFORE the strict hardware runs, so thresholds cannot be tuned to
the data afterwards.

C1  Signal        exact one-sided binomial p-value < ALPHA / m (Bonferroni over all m tests) AND
                  the whole 95% Wilson interval of the success rate lies above the noise baseline.
C2  Dominance     Shor: the k most frequent outcomes are exactly the k outcomes the ideal circuit
                  can produce. Grover: the most frequent key is the secret AND it occurs at least
                  DOMINANCE x as often as the runner-up.
C3  Fidelity      Hellinger fidelity to the ideal distribution >= the fidelity a "half-signal"
                  output would have (50% ideal + 50% uniform noise). Derived from theory, not data.
C4  Fingerprint   Grover iteration sweep 0..4: Pearson correlation with theory >= RANK_MIN (noise
                  acts as hardware = lambda*theory + (1-lambda)*uniform, a linear relation)
                  and success at the optimum (2) significantly above 3 iterations (overshoot).
C5  Layout        the same circuit placed on different physical qubits passes C1-C3 every time.
C6  Repeatability two runs of the same circuit on the same backend are statistically
                  indistinguishable: chi-square homogeneity p > REPEAT_P.
"""

from math import sqrt

from qiskit.quantum_info import hellinger_fidelity
from scipy.stats import chi2_contingency, norm, pearsonr

from .stats import p_value_above_baseline, wilson_interval

ALPHA = 0.05
DOMINANCE = 2.0
RANK_MIN = 0.9
REPEAT_P = 0.001
CRITERIA_VERSION = "strict-v1"


def _probs(counts: dict) -> dict:
    total = sum(counts.values())
    return {k: v / total for k, v in counts.items()}


def half_signal_fidelity(ideal: dict, n_bits: int) -> float:
    """Hellinger fidelity of (0.5 ideal + 0.5 uniform) to the ideal: the C3 bar."""
    dim = 2**n_bits
    keys = {format(i, f"0{n_bits}b") for i in range(dim)}
    mixed = {k: 0.5 * ideal.get(k, 0.0) + 0.5 / dim for k in keys}
    return hellinger_fidelity(mixed, {k: v for k, v in ideal.items() if v > 0})


def signal(k: int, n: int, baseline: float, m_tests: int) -> dict:
    lo, hi = wilson_interval(k, n)
    p = p_value_above_baseline(k, n, baseline)
    return {"rate": k / n, "ci95": [lo, hi], "baseline": baseline, "p_value": p,
            "alpha_corrected": ALPHA / m_tests, "pass": bool(p < ALPHA / m_tests and lo > baseline)}


def shor_dominance(counts: dict, ideal: dict) -> dict:
    support = {k for k, v in ideal.items() if v > 1e-9}
    top = {k for k, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:len(support)]}
    return {"ideal_outcomes": sorted(support), "top_outcomes": sorted(top), "pass": top == support}


def grover_dominance(counts: dict, secret: int, n_bits: int) -> dict:
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    best_key, best = ranked[0]
    runner = ranked[1][1] if len(ranked) > 1 else 0
    ratio = best / runner if runner else float("inf")
    return {"mode": int(best_key, 2), "secret": secret, "ratio_to_runner_up": ratio,
            "pass": int(best_key, 2) == secret and ratio >= DOMINANCE}


def fidelity(counts: dict, ideal: dict, n_bits: int) -> dict:
    f = hellinger_fidelity(_probs(counts), {k: v for k, v in ideal.items() if v > 0})
    bar = half_signal_fidelity(ideal, n_bits)
    return {"hellinger_fidelity": f, "threshold": bar, "pass": f >= bar}


def sweep_fingerprint(rates: list, shots: int, theory: list) -> dict:
    """rates/theory indexed by iteration count 0..len-1."""
    rho = pearsonr(rates, theory).statistic
    # two-proportion z-test: success at 2 iterations vs 3 iterations (the overshoot)
    p2, p3 = rates[2], rates[3]
    pooled = (p2 + p3) / 2
    se = sqrt(2 * pooled * (1 - pooled) / shots) or 1e-12
    p_overshoot = 1 - norm.cdf((p2 - p3) / se)
    return {"pearson": float(rho), "p_overshoot": float(p_overshoot),
            "pass": bool(rho >= RANK_MIN and p_overshoot < ALPHA)}


def repeatability(counts_a: dict, counts_b: dict) -> dict:
    keys = sorted(set(counts_a) | set(counts_b))
    table = [[counts_a.get(k, 0) for k in keys], [counts_b.get(k, 0) for k in keys]]
    table = [list(col) for col in zip(*table, strict=True) if sum(col) > 0]  # drop all-zero outcomes
    p = chi2_contingency(list(zip(*table, strict=True)))[1]
    return {"chi2_p": float(p), "pass": bool(p > REPEAT_P)}
