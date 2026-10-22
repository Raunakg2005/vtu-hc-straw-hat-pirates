"""Hardware-calibrated Q-Day: what our measured IBM noise implies for breaking RSA-2048.

The published estimates (estimates.py) assume physical error rates of about 1e-3. Here we measure the error rate
ourselves, from the Grover runs on real IBM hardware, and carry it through to the resources an RSA-2048 attack
would need.

1. Effective fidelity of a run. The measured distribution P is modelled as the ideal distribution I mixed with
   uniform noise U (global depolarising model): P = F I + (1 - F) U. F is the least-squares estimate
   F = <P - U, I - U> / |I - U|^2, with its exact multinomial standard error.
2. Effective error per two-qubit gate: eps = 1 - F^(1/g) for a circuit with g two-qubit gates. Readout and
   single-qubit errors are folded in, so eps is an upper bound on the pure two-qubit error.
   Grover is the probe: it measures every qubit it touches. In Shor N = 15 most gates act on the work register,
   whose errors barely reach the measured counting qubits, so its success does not track gate count.
3. Without error correction, a circuit of G two-qubit gates succeeds with probability ~ (1 - eps)^G.
4. With the surface code (Fowler et al. 2012), the logical error per qubit per round is
   p_L = A (eps / p_th)^((d + 1) / 2) with A = 0.1, p_th = 1e-2, and a logical qubit costs ~2 d^2 physical
   qubits. Above p_th no code distance helps. The model is deliberately simple (Gidney 2025 uses yoked surface
   codes and magic-state cultivation), so we report our estimate as a ratio against the same model at the
   paper's assumed 1e-3, and scale the paper's "< 1 million qubits" by that ratio.
"""

import json
from math import ceil, log, log10
from pathlib import Path

import numpy as np

SURFACE_A = 0.1
SURFACE_THRESHOLD = 1e-2
PUBLISHED_ERROR_RATE = 1e-3            # physical error rate assumed by Gidney 2025
PUBLISHED_PHYSICAL_QUBITS = 1_000_000  # "less than a million noisy qubits"
RSA_LOGICAL_QUBITS = 1399              # Gidney 2025
RSA_TOFFOLI = 6.5e9                    # Gidney 2025
CNOTS_PER_TOFFOLI = 6                  # standard Toffoli decomposition
RUNTIME_ROUNDS = 7 * 24 * 3600 * 1_000_000  # "< 1 week" at a 1 microsecond surface-code cycle
GROVER_PLAINTEXT = 5


# ---------------------------------------------------------------- measurement
def effective_fidelity(counts: dict, ideal: dict, n_bits: int):
    """(F, standard error) of P = F I + (1 - F) U, or None when the ideal output is itself uniform."""
    shots = sum(counts.values())
    dim = 2 ** n_bits
    keys = [format(i, f"0{n_bits}b") for i in range(dim)]
    p = np.array([counts.get(k, 0) / shots for k in keys])
    w = np.array([ideal.get(k, 0.0) for k in keys]) - 1 / dim
    norm = float(w @ w)
    if norm < 1e-12:
        return None
    coef = w / norm
    f = float(coef @ (p - 1 / dim))
    var = (float(coef**2 @ p) - float(coef @ p) ** 2) / shots  # multinomial variance of a linear statistic
    return f, max(var, 0.0) ** 0.5


def error_per_gate(fidelity: float, se: float, gates: int, z: float = 1.959964):
    """(eps, low, high) effective error per two-qubit gate with a 95% interval; None if there is no signal."""
    if gates <= 0 or fidelity <= 0:
        return None

    def eps(f):
        return 1 - min(max(f, 1e-12), 1.0) ** (1 / gates)

    return eps(fidelity), eps(fidelity + z * se), eps(fidelity - z * se)


# ---------------------------------------------------------------- extrapolation
def success_without_qec(eps: float, two_qubit_gates: float) -> float:
    """log10 of the chance that G two-qubit gates all succeed: (1 - eps)^G."""
    return two_qubit_gates * log10(1 - eps)


def max_error_without_qec(two_qubit_gates: float, success: float = 0.5) -> float:
    """Largest eps for which a G-gate circuit still succeeds with the given probability."""
    return -log(success) / two_qubit_gates


def surface_code(eps: float, logical_qubits: int = RSA_LOGICAL_QUBITS, rounds: float = RUNTIME_ROUNDS):
    """Code distance and physical qubits so that all logical qubits survive every round; None above threshold."""
    if eps >= SURFACE_THRESHOLD:
        return None
    target = 1 / (logical_qubits * rounds)
    k = ceil(log(target / SURFACE_A) / log(eps / SURFACE_THRESHOLD))  # k = (d + 1) / 2
    d = 2 * k - 1
    return {"distance": d, "physical_qubits": 2 * d * d * logical_qubits}


def rsa2048_at(eps: float) -> dict:
    """What breaking RSA-2048 (Gidney 2025) would take at an effective two-qubit error rate eps."""
    gates = RSA_TOFFOLI * CNOTS_PER_TOFFOLI
    code, reference = surface_code(eps), surface_code(PUBLISHED_ERROR_RATE)
    out = {
        "eps": eps,
        "two_qubit_gates": gates,
        "log10_success_without_qec": success_without_qec(eps, gates),
        "max_eps_without_qec": max_error_without_qec(gates),
        "below_threshold": code is not None,
    }
    out["improvement_needed_without_qec"] = eps / out["max_eps_without_qec"]
    if code:
        ratio = code["physical_qubits"] / reference["physical_qubits"]
        out.update(distance=code["distance"], model_physical_qubits=code["physical_qubits"],
                   ratio_to_published=ratio, physical_qubits=ratio * PUBLISHED_PHYSICAL_QUBITS)
    return out


# ---------------------------------------------------------------- data
def _grover_ideal(secret: int, iterations: int) -> dict:
    from qiskit.quantum_info import Statevector

    from qday.quantum import grover

    qc = grover.grover_key_search_circuit(GROVER_PLAINTEXT, grover.toy_encrypt(GROVER_PLAINTEXT, secret, 3),
                                          iterations, 3)
    probs = Statevector(qc.remove_final_measurements(inplace=False)).probabilities_dict(qargs=[0, 1, 2])
    return {k: v for k, v in probs.items() if v > 1e-12}


def grover_records(results_dir: Path) -> list:
    """Every Grover run with at least one iteration in the strict suite, with F and eps."""
    rows = []
    for path in sorted(Path(results_dir, "strict").glob("*.json")):
        job = json.loads(path.read_text(encoding="utf8"))
        for c in job["circuits"]:
            if c["kind"] != "grover" or c["iterations"] < 1:
                continue
            fit = effective_fidelity(c["counts"], _grover_ideal(c["secret"], c["iterations"]), 3)
            f, se = fit
            e = error_per_gate(f, se, c["two_qubit_gates"])
            rows.append({
                "backend": job["backend"], "hardware": bool(job.get("hardware")), "job_id": job.get("job_id"),
                "run": job.get("tag", "main"), "layout": c["layout"], "physical_qubits": c["physical_qubits"],
                "secret": c["secret"], "iterations": c["iterations"], "two_qubit_gates": c["two_qubit_gates"],
                "fidelity": f, "fidelity_se": se,
                "eps": e[0] if e else None, "eps_low": e[1] if e else None, "eps_high": e[2] if e else None,
            })
    return rows


def summarise_backends(rows: list) -> dict:
    """Per backend: the error rate of its best and worst qubit sets, and the median over all runs.

    Runs are grouped by the physical qubits they used and each set is summarised by its median, so one noisy run
    cannot stand for a whole chip.
    """
    out = {}
    for backend in sorted({r["backend"] for r in rows}):
        rs = [r for r in rows if r["backend"] == backend and r["eps"] is not None]
        sets = {}
        for r in rs:
            sets.setdefault(tuple(sorted(r["physical_qubits"])), []).append(r["eps"])
        by_set = {qubits: float(np.median(e)) for qubits, e in sets.items()}
        best_set = min(by_set, key=by_set.get)
        worst_set = max(by_set, key=by_set.get)
        eps = [r["eps"] for r in rs]
        out[backend] = {
            "hardware": rs[0]["hardware"], "runs": len(rs), "qubit_sets": len(sets),
            "no_signal": sum(1 for r in rows if r["backend"] == backend and r["eps"] is None),
            "best": by_set[best_set], "best_qubits": list(best_set),
            "median": float(np.median(eps)),
            "worst": by_set[worst_set], "worst_qubits": list(worst_set),
            "above_threshold": sum(1 for e in eps if e >= SURFACE_THRESHOLD),
        }
    return out


def calibrate(results_dir: Path) -> dict:
    """The full hardware-calibrated forecast from the saved strict-suite runs."""
    rows = grover_records(results_dir)
    machines = summarise_backends(rows)
    hardware = {b: m for b, m in machines.items() if m["hardware"]}
    return {
        "method": "global depolarising fit of Grover runs; eps = 1 - F^(1/g), readout folded in (upper bound)",
        "assumptions": {
            "surface_code": f"p_L = {SURFACE_A} (eps/{SURFACE_THRESHOLD})^((d+1)/2), 2d^2 physical qubits per logical",
            "rsa2048": f"{RSA_LOGICAL_QUBITS} logical qubits, {RSA_TOFFOLI:.1e} Toffoli x {CNOTS_PER_TOFFOLI} CNOT, "
                       f"< 1 week at 1 us per round",
            "published_error_rate": PUBLISHED_ERROR_RATE,
        },
        "runs": rows,
        "machines": machines,
        "forecast": {
            "published_assumption": rsa2048_at(PUBLISHED_ERROR_RATE),
            "best_measured": rsa2048_at(min(m["best"] for m in hardware.values())),
            "median_measured": rsa2048_at(float(np.median([m["median"] for m in hardware.values()]))),
        },
    }


def describe(f: dict) -> str:
    """One line for the forecast at a given error rate."""
    if not f["below_threshold"]:
        return f"eps = {f['eps']:.1e}: above the surface-code threshold, no code distance helps"
    return (f"eps = {f['eps']:.1e}: distance {f['distance']}, about {f['physical_qubits'] / 1e6:.1f} million "
            f"physical qubits ({f['ratio_to_published']:.1f}x the published estimate)")



__all__ = ["effective_fidelity", "error_per_gate", "success_without_qec", "max_error_without_qec", "surface_code",
           "rsa2048_at", "grover_records", "summarise_backends", "calibrate", "describe"]
