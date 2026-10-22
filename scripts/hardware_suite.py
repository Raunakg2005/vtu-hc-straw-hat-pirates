"""Rigorous hardware validation of the Shor and Grover circuits.

Suite (17 circuits x 4,000 shots, ONE job per backend):
  * Shor N = 15, 3 counting qubits, every base a in {2, 4, 7, 8, 11, 13, 14}
      a = 14 is a negative control: 14 = -1 mod 15, so it must NEVER yield a factor.
  * Shor N = 15, a = 7 with 4 counting qubits (deeper circuit)
  * Grover 3-bit key search for ALL 8 secret keys (2 iterations, the optimum)
  * Grover with 0 iterations: negative control, must look like random guessing (1/8)
For every circuit we report the success rate with a 95% Wilson interval, an exact one-sided
binomial p-value against the pure-noise / random-guess baseline, the total variation distance
(TVD) to the ideal distribution, and the success predicted by the backend's noise model.

    python scripts/hardware_suite.py submit --backend ibm_kingston
    python scripts/hardware_suite.py fetch  --backend ibm_kingston
    python scripts/hardware_suite.py simulate              # fake_marrakesh noise model
    python scripts/hardware_suite.py report                # -> results/hardware_suite.json
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qiskit.quantum_info import Statevector  # noqa: E402

from qday.config import RESULTS_DIR, runtime_service  # noqa: E402
from qday.quantum import grover, shor  # noqa: E402
from qday.quantum.runner import circuit_stats, get_backend, run_sampler, transpile_for  # noqa: E402
from qday.quantum.stats import normalise, summarise, tvd  # noqa: E402

SHOTS = 4000
PLAINTEXT = 5


def suite():
    circs = [shor.order_finding_circuit(a, 15, 3) for a in (2, 4, 7, 8, 11, 13, 14)]
    circs.append(shor.order_finding_circuit(7, 15, 4))
    for secret in range(8):
        circs.append(grover.grover_key_search_circuit(PLAINTEXT, grover.toy_encrypt(PLAINTEXT, secret, 3), 2, 3))
    circs.append(grover.grover_key_search_circuit(PLAINTEXT, grover.toy_encrypt(PLAINTEXT, 6, 3), 0, 3))
    return circs


def ideal_distribution(qc) -> dict:
    sv = Statevector(qc.remove_final_measurements(inplace=False))
    n = qc.cregs[0].size
    probs = sv.probabilities_dict(qargs=list(range(n)))
    return {k: v for k, v in probs.items() if v > 1e-12}


def analyse(name: str, counts: dict) -> dict:
    shots = sum(counts.values())
    if name.startswith("shor"):
        a = int(name.split("_a")[1])
        n = len(next(iter(counts)))
        r = shor.analyse_counts(counts, a, 15, n)
        k = round(r["success_probability"] * shots)
        return {"kind": "shor", "label": f"Shor N=15 a={a} ({n} counting qubits)", "a": a,
                "result": f"factors {r['factors']}" if r["factors"] else "no factor (expected for a=14)",
                "control": a == 14, **summarise(k, shots, r["random_noise_baseline"])}
    m = grover.parse_name(name)
    r = grover.analyse_counts(counts, m["plaintext"], m["ciphertext"], m["iterations"], 3)
    secret = next(s for s in range(8) if grover.toy_encrypt(PLAINTEXT, s, 3) == m["ciphertext"])
    k = round(r["success_probability"] * shots)
    return {"kind": "grover", "label": f"Grover secret={secret} ({m['iterations']} iterations)", "secret": secret,
            "result": ("no search: near-uniform, as expected" if m["iterations"] == 0 else
                       f"recovered {r['recovered_key']} ({'correct' if r['key_is_correct'] else 'wrong'})"),
            "recovered_correct": r["key_is_correct"], "control": m["iterations"] == 0,
            "theory": r["theoretical_success"], **summarise(k, shots, r["random_guess_baseline"])}


def job_file(backend):
    return RESULTS_DIR / f"suite_job_{backend}.json"


def submit(backend_name):
    from qiskit_ibm_runtime import SamplerV2

    backend = get_backend(backend_name)
    circs = suite()
    isa = transpile_for(circs, backend)
    job = SamplerV2(mode=backend).run(isa, shots=SHOTS)
    meta = {"job_id": job.job_id(), "backend": backend.name, "shots": SHOTS,
            "submitted": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "circuits": [{"name": c.name, **circuit_stats(i)} for c, i in zip(circs, isa, strict=True)]}
    RESULTS_DIR.mkdir(exist_ok=True)
    job_file(backend.name).write_text(json.dumps(meta, indent=1), encoding="utf8")
    print(f"submitted {meta['job_id']} to {backend.name}")


def fetch(backend_name):
    meta = json.loads(job_file(backend_name).read_text(encoding="utf8"))
    job = runtime_service().job(meta["job_id"])
    print(f"waiting for {meta['job_id']} on {backend_name}: {job.status()}")
    result = job.result()
    try:
        meta["quantum_seconds"] = job.usage()
    except Exception:
        meta["quantum_seconds"] = None
    for entry, pub in zip(meta["circuits"], result, strict=True):
        entry["counts"] = pub.data.meas.get_counts()
    meta["hardware"] = True
    job_file(backend_name).write_text(json.dumps(meta, indent=1), encoding="utf8")
    print("saved", job_file(backend_name))


def simulate():
    res = run_sampler(suite(), "fake_marrakesh", shots=SHOTS)
    res["backend"] = "fake_marrakesh"
    job_file("fake_marrakesh").write_text(json.dumps(res, indent=1), encoding="utf8")
    print("saved", job_file("fake_marrakesh"))


def report():
    ideal = [ideal_distribution(c) for c in suite()]  # by position: names repeat (a=7 at 3 and 4 qubits)
    runs = {}
    for path in sorted(RESULTS_DIR.glob("suite_job_*.json")):
        data = json.loads(path.read_text(encoding="utf8"))
        if not all("counts" in c for c in data["circuits"]):
            continue
        rows = []
        for i, c in enumerate(data["circuits"]):
            row = analyse(c["name"], c["counts"])
            row.update(name=c["name"], two_qubit_gates=c["two_qubit_gates"], depth=c["depth"],
                       tvd_to_ideal=tvd(normalise(c["counts"]), ideal[i]))
            rows.append(row)
        runs[data["backend"]] = {"backend": data["backend"], "job_id": data.get("job_id"),
                                 "hardware": data.get("hardware", False),
                                 "quantum_seconds": data.get("quantum_seconds"), "rows": rows}
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "shots": SHOTS, "runs": runs}
    (RESULTS_DIR / "hardware_suite.json").write_text(json.dumps(out, indent=1), encoding="utf8")
    for be, run in runs.items():
        print(f"\n== {be} (hardware={run['hardware']}, QPU s={run['quantum_seconds']})")
        for r in run["rows"]:
            flag = "control" if r["control"] else ("PASS" if r["significant"] else "FAIL")
            print(f"  {r['label']:38s} 2q={r['two_qubit_gates']:3d} rate={r['rate']:.3f} "
                  f"CI=[{r['ci95'][0]:.3f},{r['ci95'][1]:.3f}] base={r['baseline']:.3f} "
                  f"p={r['p_value']:.1e} TVD={r['tvd_to_ideal']:.3f}  {r['result']}  [{flag}]")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["submit", "fetch", "simulate", "report"])
    ap.add_argument("--backend", default="ibm_kingston")
    args = ap.parse_args()
    {"submit": lambda: submit(args.backend), "fetch": lambda: fetch(args.backend), "simulate": simulate,
     "report": report}[args.action]()
