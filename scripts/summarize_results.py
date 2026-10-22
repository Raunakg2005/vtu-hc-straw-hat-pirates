"""Regenerate docs/RESULTS.md and results/noise_calibration.json from the raw hardware files in results/.

    python scripts/summarize_results.py          # writes both files
    python scripts/summarize_results.py --check  # exit 1 if either is out of date (used by the tests)

Every number in RESULTS.md is recomputed from the saved counts, so the document cannot drift from the data.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from qday.forecast import calibrated  # noqa: E402
from qday.quantum import shor  # noqa: E402

RESULTS = ROOT / "results"
DOC = ROOT / "docs" / "RESULTS.md"
CALIBRATION = RESULTS / "noise_calibration.json"
HARDWARE = ("ibm_fez", "ibm_kingston", "ibm_marrakesh")


def load(name):
    return json.loads((RESULTS / name).read_text(encoding="utf8"))


def pct(x, digits=1):
    return f"{100 * x:.{digits}f}%"


def cell(row):
    lo, hi = row["ci95"]
    return f"{pct(row['rate'])} ({pct(lo, 1)}–{pct(hi, 1)})"


def ideal_success(row):
    """Success the noiseless circuit would score."""
    if row["kind"] == "grover":
        return row.get("theory", 0.125)
    import hardware_suite

    circuits = {c.name: c for c in hardware_suite.suite()}
    qc = circuits[row["name"]] if not row["label"].endswith("(4 counting qubits)") else \
        shor.order_finding_circuit(row["a"], 15, 4)
    ideal = hardware_suite.ideal_distribution(qc)
    counts = {k: round(v * 1_000_000) for k, v in ideal.items()}
    return shor.analyse_counts(counts, row["a"], 15, len(next(iter(counts))))["success_probability"]


def jobs_table():
    first = load("hardware_run.json")
    suite = load("hardware_suite.json")
    rows = [("First run", first["backend"], first["job_id"], first["submitted"][:10], len(first["circuits"]),
             first["quantum_seconds"])]
    for backend in HARDWARE:
        job = load(f"suite_job_{backend}.json")
        rows.append(("Validation suite", backend, job["job_id"], job["submitted"][:10], len(job["circuits"]),
                     suite["runs"][backend]["quantum_seconds"]))
    for path in sorted((RESULTS / "strict").glob("ibm_*.json")):
        job = json.loads(path.read_text(encoding="utf8"))
        rows.append((f"Strict suite ({job['tag']})", job["backend"], job["job_id"], job["submitted"][:10],
                     len(job["circuits"]), job["quantum_seconds"]))
    total = sum(r[5] for r in rows)
    lines = ["| Run | Backend | Job ID | Date | Circuits | QPU seconds |", "| :--- | :--- | :--- | :--- | ---: | ---: |"]
    lines += [f"| {r[0]} | `{r[1]}` | `{r[2]}` | {r[3]} | {r[4]} | {r[5]} |" for r in rows]
    lines.append(f"| **Total** | | | | **{sum(r[4] for r in rows)}** | **{total}** |")
    return "\n".join(lines), total


def suite_table():
    suite = load("hardware_suite.json")["runs"]
    model = suite["fake_marrakesh"]["rows"]
    lines = ["| Circuit | 2-qubit gates | Random / noise baseline | Ideal | Noise model (`fake_marrakesh`) | "
             "`ibm_fez` | `ibm_kingston` | `ibm_marrakesh` |",
             "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for i, base in enumerate(suite["ibm_fez"]["rows"]):
        hw = [suite[b]["rows"][i] for b in HARDWARE]
        gates = "/".join(sorted({str(r["two_qubit_gates"]) for r in hw}))
        label = base["label"] + (" — control" if base["control"] else "")
        lines.append(f"| {label} | {gates} | {pct(base['baseline'])} | {pct(ideal_success(base))} | "
                     f"{pct(model[i]['rate'])} | " + " | ".join(cell(r) for r in hw) + " |")
    return "\n".join(lines)


def strict_table():
    strict = load("hardware_strict.json")["backends"]
    lines = ["| Backend | Job ID | Every rule (14 tests) | Shor | Grover | Grover curve vs theory (r) | Repeat run |",
             "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |"]
    for backend in HARDWARE:
        b = strict[backend]
        tests = [r for r in b["rows"] if not r["control"]]
        shor_ok = sum(r["pass"] for r in tests if r["test"].startswith("Shor"))
        shor_n = sum(1 for r in tests if r["test"].startswith("Shor"))
        gr_ok = sum(r["pass"] for r in tests if r["test"].startswith("Grover"))
        gr_n = sum(1 for r in tests if r["test"].startswith("Grover"))
        repeat = "pass" if (b["C6_repeatability"] or {}).get("pass") else ("fail" if b["C6_repeatability"] else "not run")
        lines.append(f"| `{backend}` | `{b['job_id']}` | {b['summary']['tests_passed']} / {b['summary']['tests']} | "
                     f"{shor_ok} / {shor_n} | {gr_ok} / {gr_n} | {b['C4_fingerprint']['pearson']:.2f} | {repeat} |")
    return "\n".join(lines)


def noise_tables(cal):
    m = cal["machines"]
    lines = ["| Backend | Grover runs | Best qubit set | Error per 2-qubit gate (best set) | Median, all runs | "
             "Worst qubit set | Error (worst set) | Runs above 1% threshold |",
             "| :--- | ---: | :--- | ---: | ---: | :--- | ---: | ---: |"]
    for name in ("fake_marrakesh",) + HARDWARE:
        x = m[name]
        label = f"`{name}`" + (" (noise model)" if not x["hardware"] else "")
        lines.append(f"| {label} | {x['runs']} | {x['best_qubits']} | {x['best']:.1e} | {x['median']:.1e} | "
                     f"{x['worst_qubits']} | {x['worst']:.1e} | {x['above_threshold']} |")
    per_run = ["| Backend | Run | Qubits | Iterations | 2-qubit gates | Effective fidelity F | Error per gate (95% CI) |",
               "| :--- | :--- | :--- | ---: | ---: | ---: | :--- |"]
    for r in cal["runs"]:
        if not r["hardware"]:
            continue
        err = "no signal" if r["eps"] is None else f"{r['eps']:.1e} ({r['eps_low']:.1e}–{r['eps_high']:.1e})"
        per_run.append(f"| `{r['backend']}` | {r['run']} / {r['layout']} | {r['physical_qubits']} | {r['iterations']} | "
                       f"{r['two_qubit_gates']} | {r['fidelity']:.3f} ± {r['fidelity_se']:.3f} | {err} |")
    f = cal["forecast"]
    fc = ["| Error per 2-qubit gate | Surface-code distance | Physical qubits for RSA-2048 | vs published | "
          "Without error correction |", "| :--- | ---: | ---: | ---: | :--- |"]
    for label, key in (("Published assumption", "published_assumption"), ("Best measured qubits", "best_measured"),
                       ("Median measured", "median_measured")):
        x = f[key]
        fc.append(f"| {label}: {x['eps']:.1e} | {x['distance']} | {x['physical_qubits'] / 1e6:.1f} million | "
                  f"{x['ratio_to_published']:.1f}× | needs {x['improvement_needed_without_qec']:.0e}× lower error |")
    worst = m["ibm_marrakesh"]["worst"]
    fc.append(f"| `ibm_marrakesh` qubits {m['ibm_marrakesh']['worst_qubits']}: {worst:.1e} | — | impossible: above the "
              f"surface-code threshold | — | — |")
    return "\n".join(lines), "\n".join(per_run), "\n".join(fc)


def render():
    cal = calibrated.calibrate(RESULTS)
    jobs, total_seconds = jobs_table()
    machines, per_run, forecast = noise_tables(cal)
    doc = f"""# Hardware results

Generated by `scripts/summarize_results.py` from the raw counts in `results/`. Do not edit by hand.

## Jobs on IBM quantum hardware

{jobs}

## Validation suite: every circuit on three machines

Success rate with its 95% Wilson interval, 4,000 shots each. A test passes only if the whole interval is above
the random / noise baseline. The ideal column is the noiseless circuit; the noise model is Qiskit's
`fake_marrakesh` snapshot of IBM's published calibration.

{suite_table()}

## Strict suite: pass rules fixed in code before the runs (`strict-v1`)

{strict_table()}

## Measured noise: effective error per two-qubit gate

From every Grover run (Grover measures all the qubits it uses). Each run's output is fitted as the ideal
distribution mixed with uniform noise, `P = F·I + (1 − F)·U`, and `ε = 1 − F^(1/g)` for `g` two-qubit gates.
Readout and single-qubit errors are folded into `ε`, so it is an upper bound. Runs are grouped by the physical
qubits they used.

{machines}

<details><summary>Every hardware run</summary>

{per_run}

</details>

## Hardware-calibrated forecast for RSA-2048

Gidney 2025: 1,399 logical qubits and 6.5 × 10⁹ Toffoli gates (× 6 CNOTs each), under one week. Surface code:
`p_L = 0.1 (ε / 0.01)^((d+1)/2)`, about `2d²` physical qubits per logical qubit. The model is simpler than the
paper's, so physical qubits are scaled from the paper's "under one million" at its assumed `ε = 10⁻³`.

{forecast}
"""
    payload = dict(cal, qpu_seconds_total=total_seconds)
    # 6 significant figures: identical on every platform, so the up-to-date check is stable in CI
    return doc, json.dumps(_round(payload), indent=1, sort_keys=True) + "\n"


def _round(value):
    if isinstance(value, float):
        return float(f"{value:.6g}")
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_round(v) for v in value]
    return value


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if the files on disk are out of date")
    args = ap.parse_args(argv)
    doc, cal = render()
    if args.check:
        stale = [p.name for p, text in ((DOC, doc), (CALIBRATION, cal))
                 if not p.exists() or p.read_text(encoding="utf8") != text]
        if stale:
            raise SystemExit(f"out of date: {', '.join(stale)}; run python scripts/summarize_results.py")
        print("up to date")
        return
    DOC.parent.mkdir(exist_ok=True)
    DOC.write_text(doc, encoding="utf8")
    CALIBRATION.write_text(cal, encoding="utf8")
    print("wrote", DOC.relative_to(ROOT), "and", CALIBRATION.relative_to(ROOT))


if __name__ == "__main__":
    main()
