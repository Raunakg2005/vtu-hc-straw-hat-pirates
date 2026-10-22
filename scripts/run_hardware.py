"""Submit the Shor + Grover circuits to IBM Quantum hardware as ONE batched job, or fetch it.

    python scripts/run_hardware.py submit --backend ibm_least_busy
    python scripts/run_hardware.py fetch            # waits for the job, saves results/hardware_run.json
    python scripts/run_hardware.py simulate         # same circuits on fake_marrakesh -> results/fake_run.json
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qday.config import RESULTS_DIR, runtime_service  # noqa: E402
from qday.quantum.grover import grover_key_search_circuit, toy_encrypt  # noqa: E402
from qday.quantum.runner import (  # noqa: E402
    circuit_stats,
    get_backend,
    run_sampler,
    save_result,
    transpile_for,
)
from qday.quantum.shor import order_finding_circuit  # noqa: E402

SHOTS = 4000
JOB_FILE = RESULTS_DIR / "hardware_job.json"


def experiment_circuits():
    secret_key, plaintext = 6, 5
    ciphertext = toy_encrypt(plaintext, secret_key, 3)
    return [
        order_finding_circuit(7, 15, 3),
        order_finding_circuit(2, 15, 3),
        order_finding_circuit(13, 15, 3),
        grover_key_search_circuit(plaintext, ciphertext, 1, 3),
        grover_key_search_circuit(plaintext, ciphertext, 2, 3),
    ]


def submit(backend_name: str):
    from qiskit_ibm_runtime import SamplerV2

    backend = get_backend(backend_name)
    circuits = experiment_circuits()
    isa = transpile_for(circuits, backend)
    job = SamplerV2(mode=backend).run(isa, shots=SHOTS)
    meta = {
        "job_id": job.job_id(),
        "backend": backend.name,
        "shots": SHOTS,
        "submitted": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "circuits": [{"name": c.name, **circuit_stats(i)} for c, i in zip(circuits, isa, strict=True)],
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    JOB_FILE.write_text(json.dumps(meta, indent=1), encoding="utf8")
    print(f"submitted job {meta['job_id']} to {backend.name}; status: {job.status()}")


def fetch():
    meta = json.loads(JOB_FILE.read_text(encoding="utf8"))
    job = runtime_service().job(meta["job_id"])
    print(f"job {meta['job_id']} on {meta['backend']}: {job.status()} (waiting...)")
    result = job.result()
    out = {**meta, "hardware": True, "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        out["quantum_seconds"] = job.usage()
    except Exception:
        out["quantum_seconds"] = None
    for entry, pub in zip(out["circuits"], result, strict=True):
        entry["counts"] = pub.data.meas.get_counts()
    print("saved", save_result(out, "hardware_run.json"))


def simulate():
    res = run_sampler(experiment_circuits(), "fake_marrakesh", shots=SHOTS)
    print("saved", save_result(res, "fake_run.json"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["submit", "fetch", "simulate"])
    ap.add_argument("--backend", default="ibm_least_busy")
    args = ap.parse_args()
    {"submit": lambda: submit(args.backend), "fetch": fetch, "simulate": simulate}[args.action]()
