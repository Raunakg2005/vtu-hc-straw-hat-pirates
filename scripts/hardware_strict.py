"""Strict hardware validation (criteria pre-registered in qday/quantum/validation.py).

Per backend, ONE job of 19 circuits x 4,000 shots:
  * Shor N = 15 (3 counting qubits) for a = 2, 4, 7, 8, 11, 13            -> C1 C2 C3
  * Shor a = 14 negative control (14 = -1 mod 15: must never factor)
  * Grover 3-bit, 2 iterations, 3 BLINDED secrets drawn at submit time      -> C1 C2 C3
  * Grover sweep 0..4 iterations on one more blinded secret                 -> C4 (+ 0-iteration control)
  * Shor a = 7 and Grover (sweep secret, 2 iterations) re-placed on 2 other
    qubit regions of the chip (lowest-readout-error seeds, BFS-connected)    -> C5
Plus one repeat job of the identical compiled circuits on one backend     -> C6

    python scripts/hardware_strict.py simulate                    # dry run on fake_marrakesh
    python scripts/hardware_strict.py submit --backend ibm_kingston [--repeat]
    python scripts/hardware_strict.py fetch                        # all pending strict jobs
    python scripts/hardware_strict.py report                       # -> results/hardware_strict.json
"""

import argparse
import json
import secrets
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qiskit.quantum_info import Statevector  # noqa: E402
from qiskit.transpiler import generate_preset_pass_manager  # noqa: E402

from qday.config import RESULTS_DIR, runtime_service  # noqa: E402
from qday.quantum import grover, shor  # noqa: E402
from qday.quantum import validation as v  # noqa: E402
from qday.quantum.runner import circuit_stats, get_backend  # noqa: E402

SHOTS = 4000
PLAINTEXT = 5
SWEEP = [0, 1, 2, 3, 4]
MAX_READOUT_ERROR = 0.05  # qubits worse than this are never used for the manual region layouts
STRICT_DIR = RESULTS_DIR / "strict"


# ---------------------------------------------------------------- plan
def blinded_secrets(k: int) -> list:
    out = []
    while len(out) < k:
        s = secrets.randbelow(8)
        if s not in out:
            out.append(s)
    return out


def plan(seed_secrets=None):
    """List of (circuit, meta). Secrets are drawn at random unless given (for dry runs)."""
    keys = seed_secrets or blinded_secrets(4)
    items = []
    for a in (2, 4, 7, 8, 11, 13, 14):
        items.append((shor.order_finding_circuit(a, 15, 3),
                      {"kind": "shor", "a": a, "control": a == 14, "layout": "auto"}))
    for s in keys[:3]:
        c = grover.toy_encrypt(PLAINTEXT, s, 3)
        items.append((grover.grover_key_search_circuit(PLAINTEXT, c, 2, 3),
                      {"kind": "grover", "secret": s, "iterations": 2, "control": False, "layout": "auto"}))
    sweep_secret = keys[3]
    c = grover.toy_encrypt(PLAINTEXT, sweep_secret, 3)
    for it in SWEEP:
        items.append((grover.grover_key_search_circuit(PLAINTEXT, c, it, 3),
                      {"kind": "grover", "secret": sweep_secret, "iterations": it, "control": it == 0,
                       "layout": "auto", "sweep": True}))
    for region in ("region-1", "region-2"):
        items.append((shor.order_finding_circuit(7, 15, 3),
                      {"kind": "shor", "a": 7, "control": False, "layout": region}))
        items.append((grover.grover_key_search_circuit(PLAINTEXT, c, 2, 3),
                      {"kind": "grover", "secret": sweep_secret, "iterations": 2, "control": False,
                       "layout": region}))
    return items


def region_layout(backend, n: int, region: int) -> list:
    """n connected physical qubits grown from the best-readout qubit in one third of the chip."""
    target = backend.target
    nq = backend.num_qubits

    def ro_err(q):
        try:
            return target["measure"][(q,)].error or 1.0
        except Exception:
            return 1.0

    lo, hi = region * nq // 3, (region + 1) * nq // 3
    seed = min(range(lo, hi), key=ro_err)
    cmap = backend.coupling_map
    seen, order, queue = {seed}, [seed], deque([seed])
    while queue and len(order) < n:
        q = queue.popleft()
        for nb in sorted(cmap.neighbors(q), key=ro_err):
            # skip defective qubits (the dry run found one with 47% readout error)
            if nb not in seen and len(order) < n and ro_err(nb) <= MAX_READOUT_ERROR:
                seen.add(nb)
                order.append(nb)
                queue.append(nb)
    return order


def compile_plan(items, backend):
    auto = generate_preset_pass_manager(optimization_level=3, backend=backend, seed_transpiler=7)
    out = []
    for qc, meta in items:
        if meta["layout"] == "auto":
            isa = auto.run(qc)
        else:
            region = int(meta["layout"].split("-")[1])
            layout = region_layout(backend, qc.num_qubits, region)
            pm = generate_preset_pass_manager(optimization_level=3, backend=backend, seed_transpiler=7,
                                              initial_layout=layout)
            isa = pm.run(qc)
            meta = {**meta, "physical_qubits": layout}
        if "physical_qubits" not in meta:
            meta = {**meta, "physical_qubits": sorted({isa.find_bit(q).index for inst in isa.data
                                                        for q in inst.qubits})[:qc.num_qubits]}
        out.append((qc, isa, {**meta, **circuit_stats(isa)}))
    return out


# ---------------------------------------------------------------- run
def _save(name, data):
    STRICT_DIR.mkdir(parents=True, exist_ok=True)
    (STRICT_DIR / name).write_text(json.dumps(data, indent=1), encoding="utf8")


def submit(backend_name: str, repeat: bool = False):
    from qiskit_ibm_runtime import SamplerV2

    backend = get_backend(backend_name)
    compiled = compile_plan(plan(), backend)
    jobs = [("main", SamplerV2(mode=backend).run([isa for _, isa, _ in compiled], shots=SHOTS))]
    if repeat:
        jobs.append(("repeat", SamplerV2(mode=backend).run([isa for _, isa, _ in compiled], shots=SHOTS)))
    for tag, job in jobs:
        _save(f"{backend.name}_{tag}.json", {
            "backend": backend.name, "tag": tag, "job_id": job.job_id(), "shots": SHOTS, "hardware": True,
            "criteria": v.CRITERIA_VERSION, "submitted": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "circuits": [m for _, _, m in compiled]})
        print(f"submitted {tag} job {job.job_id()} to {backend.name}")


def fetch():
    service = runtime_service()
    for path in sorted(STRICT_DIR.glob("ibm_*.json")):
        data = json.loads(path.read_text(encoding="utf8"))
        if all("counts" in c for c in data["circuits"]):
            continue
        job = service.job(data["job_id"])
        print(f"waiting for {data['backend']} {data['tag']} {data['job_id']}: {job.status()}")
        result = job.result()
        try:
            data["quantum_seconds"] = job.usage()
        except Exception:
            data["quantum_seconds"] = None
        for meta, pub in zip(data["circuits"], result, strict=True):
            meta["counts"] = pub.data.meas.get_counts()
        path.write_text(json.dumps(data, indent=1), encoding="utf8")
        print("saved", path.name)


def simulate():
    from qiskit_ibm_runtime import SamplerV2

    backend = get_backend("fake_marrakesh")
    compiled = compile_plan(plan(seed_secrets=[1, 3, 6, 4]), backend)
    for tag, seed in (("main", 11), ("repeat", 12)):
        res = SamplerV2(mode=backend, options={"simulator": {"seed_simulator": seed}}).run(
            [isa for _, isa, _ in compiled], shots=SHOTS).result()
        circuits = [{**m, "counts": pub.data.meas.get_counts()} for (_, _, m), pub in zip(compiled, res, strict=True)]
        _save(f"fake_marrakesh_{tag}.json", {"backend": "fake_marrakesh", "tag": tag, "shots": SHOTS,
                                             "hardware": False, "criteria": v.CRITERIA_VERSION,
                                             "circuits": circuits})
    print("saved dry run")


# ---------------------------------------------------------------- analyse
def ideal_for(meta):
    if meta["kind"] == "shor":
        qc = shor.order_finding_circuit(meta["a"], 15, 3)
    else:
        qc = grover.grover_key_search_circuit(PLAINTEXT, grover.toy_encrypt(PLAINTEXT, meta["secret"], 3),
                                              meta["iterations"], 3)
    probs = Statevector(qc.remove_final_measurements(inplace=False)).probabilities_dict(qargs=[0, 1, 2])
    return {k: p for k, p in probs.items() if p > 1e-12}


def evaluate(meta, m_tests):
    counts, shots = meta["counts"], sum(meta["counts"].values())
    ideal = ideal_for(meta)
    if meta["kind"] == "shor":
        r = shor.analyse_counts(counts, meta["a"], 15, 3)
        k = round(r["success_probability"] * shots)
        row = {"test": f"Shor a={meta['a']}", "baseline": r["random_noise_baseline"],
               "result": f"factors {r['factors']}" if r["factors"] else "no factor"}
        if meta["control"]:
            return {**row, "control": True, "pass": k == 0, "rate": k / shots}
        crit = {"C1": v.signal(k, shots, r["random_noise_baseline"], m_tests),
                "C2": v.shor_dominance(counts, ideal), "C3": v.fidelity(counts, ideal, 3)}
    else:
        r = grover.analyse_counts(counts, PLAINTEXT, grover.toy_encrypt(PLAINTEXT, meta["secret"], 3),
                                  meta["iterations"], 3)
        k = round(r["success_probability"] * shots)
        row = {"test": f"Grover key={meta['secret']} it={meta['iterations']}", "baseline": 0.125,
               "result": f"mode {r['recovered_key']}"}
        if meta["control"]:
            lo, hi = v.wilson_interval(k, shots)
            return {**row, "control": True, "pass": lo <= 0.125 <= hi, "rate": k / shots}
        crit = {"C1": v.signal(k, shots, 0.125, m_tests), "C2": v.grover_dominance(counts, meta["secret"], 3),
                "C3": v.fidelity(counts, ideal, 3)}
    return {**row, "control": False, "rate": k / shots, "criteria": crit,
            "pass": all(c["pass"] for c in crit.values())}


def is_sig_test(m):
    return not m["control"] and not (m.get("sweep") and m["iterations"] != 2)


def report():
    runs = [json.loads(p.read_text(encoding="utf8")) for p in sorted(STRICT_DIR.glob("*.json"))]
    runs = [r for r in runs if all("counts" in c for c in r["circuits"])]
    hw = [r for r in runs if r["hardware"]] or runs
    m_tests = sum(is_sig_test(m) for r in hw if r["tag"] == "main" for m in r["circuits"])
    out = {"criteria": v.CRITERIA_VERSION, "alpha": v.ALPHA, "m_tests": m_tests,
           "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "backends": {}}
    for run in runs:
        if run["tag"] != "main":
            continue
        be = run["backend"]
        rows = []
        for meta in run["circuits"]:
            if meta.get("sweep") and meta["iterations"] not in (0, 2):
                continue
            rows.append({**evaluate(meta, m_tests), "layout": meta["layout"],
                         "physical_qubits": meta.get("physical_qubits"), "two_qubit_gates": meta["two_qubit_gates"]})
        sweep = sorted((m for m in run["circuits"] if m.get("sweep")), key=lambda m: m["iterations"])
        rates = [grover.analyse_counts(m["counts"], PLAINTEXT, grover.toy_encrypt(PLAINTEXT, m["secret"], 3),
                                       m["iterations"], 3)["success_probability"] for m in sweep]
        theory = [grover.theoretical_success(it, 3) for it in SWEEP]
        c4 = {**v.sweep_fingerprint(rates, run["shots"], theory), "rates": rates, "theory": theory,
              "secret": sweep[0]["secret"]}
        layout_rows = [r for r in rows if r["layout"] != "auto"]
        c5 = {"pass": all(r["pass"] for r in layout_rows), "n": len(layout_rows)}
        rep = next((r for r in runs if r["backend"] == be and r["tag"] == "repeat"), None)
        c6 = None
        if rep:
            pairs = [v.repeatability(a["counts"], b["counts"]) for a, b in zip(run["circuits"], rep["circuits"], strict=True)]
            c6 = {"pass": all(p["pass"] for p in pairs), "n": len(pairs),
                  "min_p": min(p["chi2_p"] for p in pairs), "n_pass": sum(p["pass"] for p in pairs)}
        tests = [r for r in rows if not r["control"]]
        out["backends"][be] = {
            "hardware": run["hardware"], "job_id": run.get("job_id"),
            "quantum_seconds": (run.get("quantum_seconds") or 0) + ((rep or {}).get("quantum_seconds") or 0),
            "rows": rows, "C4_fingerprint": c4, "C5_layout": c5, "C6_repeatability": c6,
            "summary": {"tests_passed": sum(r["pass"] for r in tests), "tests": len(tests),
                        "controls_ok": all(r["pass"] for r in rows if r["control"]),
                        **{f"{c}_passed": sum(r["criteria"][c]["pass"] for r in tests) for c in ("C1", "C2", "C3")}}}
    (RESULTS_DIR / "hardware_strict.json").write_text(json.dumps(out, indent=1), encoding="utf8")
    print(f"criteria {out['criteria']}  alpha/m = {v.ALPHA}/{m_tests}")
    for be, b in out["backends"].items():
        s = b["summary"]
        print(f"\n== {be} (hardware={b['hardware']}, QPU s={b['quantum_seconds']})")
        print(f"   all criteria: {s['tests_passed']}/{s['tests']} | C1 {s['C1_passed']} C2 {s['C2_passed']} "
              f"C3 {s['C3_passed']} | controls ok: {s['controls_ok']}")
        for r in b["rows"]:
            if r["control"]:
                print(f"   [control] {r['test']:22s} rate={r['rate']:.3f} -> {'ok' if r['pass'] else 'FAIL'}")
                continue
            c = r["criteria"]
            print(f"   {r['test']:22s} {r['layout']:8s} 2q={r['two_qubit_gates']:3d} rate={r['rate']:.3f} "
                  f"C1={'P' if c['C1']['pass'] else 'F'} C2={'P' if c['C2']['pass'] else 'F'} "
                  f"C3={'P' if c['C3']['pass'] else 'F'} (F={c['C3']['hellinger_fidelity']:.3f} "
                  f">= {c['C3']['threshold']:.3f})")
        c4 = b["C4_fingerprint"]
        print(f"   C4 sweep key={c4['secret']}: rates={[round(x, 3) for x in c4['rates']]} "
              f"pearson={c4['pearson']:.3f} overshoot p={c4['p_overshoot']:.1e} -> {'PASS' if c4['pass'] else 'FAIL'}")
        print(f"   C5 layouts: {'PASS' if b['C5_layout']['pass'] else 'FAIL'} ({b['C5_layout']['n']} circuits)")
        if b["C6_repeatability"]:
            c6 = b["C6_repeatability"]
            print(f"   C6 repeat: {c6['n_pass']}/{c6['n']} circuits agree (min chi2 p={c6['min_p']:.3g}) "
                  f"-> {'PASS' if c6['pass'] else 'FAIL'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["simulate", "submit", "fetch", "report"])
    ap.add_argument("--backend", default="ibm_kingston")
    ap.add_argument("--repeat", action="store_true")
    a = ap.parse_args()
    {"simulate": simulate, "submit": lambda: submit(a.backend, a.repeat), "fetch": fetch, "report": report}[a.action]()
