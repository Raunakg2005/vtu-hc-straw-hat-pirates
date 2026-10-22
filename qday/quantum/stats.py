"""Statistics for judging hardware runs honestly.

* Wilson score interval: 95% confidence interval for a success probability from k/n shots.
* One-sided exact binomial test: how likely is k or more successes if the device were only
  producing the baseline rate p0 (pure noise / random guessing)? A tiny p-value means the
  quantum signal is real.
* Total variation distance (TVD) between two outcome distributions: 0 = identical, 1 = disjoint.
"""

from math import sqrt

from scipy.stats import binomtest


def wilson_interval(k: int, n: int, z: float = 1.959964) -> tuple:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    lo, hi = centre - half, centre + half
    # the interval must contain the observed rate; float rounding can miss it at k = 0 or k = n
    return (max(0.0, min(lo, p)), min(1.0, max(hi, p)))


def p_value_above_baseline(k: int, n: int, p0: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p0)."""
    return binomtest(k, n, p0, alternative="greater").pvalue


def normalise(counts: dict) -> dict:
    total = sum(counts.values())
    return {k: v / total for k, v in counts.items()} if total else {}


def tvd(p: dict, q: dict) -> float:
    keys = set(p) | set(q)
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys)


def summarise(k: int, n: int, p0: float) -> dict:
    lo, hi = wilson_interval(k, n)
    return {"successes": k, "shots": n, "rate": k / n if n else 0.0, "ci95": [lo, hi],
            "baseline": p0, "p_value": p_value_above_baseline(k, n, p0),
            "significant": lo > p0}
