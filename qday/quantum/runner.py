"""Run circuits on the ideal simulator, a noisy fake IBM backend, or real IBM Quantum hardware.

backend names:
  "aer"              ideal AerSimulator
  "fake_marrakesh"   noise model of ibm_marrakesh (also fake_fez, fake_torino, fake_brisbane)
  "ibm_<name>"       real hardware via Qiskit Runtime (e.g. ibm_kingston, ibm_marrakesh)
  "ibm_least_busy"   real hardware, least busy backend available to the account
"""

import json
import time
from datetime import datetime, timezone

from qiskit.transpiler import generate_preset_pass_manager

from ..config import RESULTS_DIR

FAKE_BACKENDS = {
    "fake_marrakesh": "FakeMarrakesh",
    "fake_fez": "FakeFez",
    "fake_torino": "FakeTorino",
    "fake_brisbane": "FakeBrisbane",
}


def get_backend(name: str):
    if name == "aer":
        from qiskit_aer import AerSimulator

        return AerSimulator()
    if name in FAKE_BACKENDS:
        from qiskit_ibm_runtime import fake_provider

        return getattr(fake_provider, FAKE_BACKENDS[name])()
    if name.startswith("ibm_"):
        from ..config import runtime_service

        service = runtime_service()
        if name == "ibm_least_busy":
            return service.least_busy(simulator=False, operational=True)
        return service.backend(name)
    raise ValueError(f"unknown backend {name!r}")


def is_hardware(backend) -> bool:
    return backend.__class__.__name__ == "IBMBackend"


def transpile_for(circuits, backend, optimization_level: int = 3, seed: int = 7):
    pm = generate_preset_pass_manager(
        optimization_level=optimization_level, backend=backend, seed_transpiler=seed
    )
    return [pm.run(c) for c in circuits]


def circuit_stats(isa_circuit) -> dict:
    multi = sum(1 for inst in isa_circuit.data
                if len(inst.qubits) >= 2 and inst.operation.name not in ("barrier", "measure"))
    return {"depth": isa_circuit.depth(), "two_qubit_gates": int(multi), "num_qubits_used": len(
        {q for inst in isa_circuit.data for q in inst.qubits})}


def run_sampler(circuits, backend_name: str = "aer", shots: int = 4000, wait: bool = True):
    """Transpile and run circuits in ONE job. Returns a result dict (or the job if wait=False)."""
    from qiskit_ibm_runtime import SamplerV2

    backend = get_backend(backend_name)
    isa = transpile_for(circuits, backend)
    sampler = SamplerV2(mode=backend)
    t0 = time.time()
    job = sampler.run(isa, shots=shots)
    if not wait:
        return job
    result = job.result()
    out = {
        "backend": getattr(backend, "name", backend_name),
        "hardware": is_hardware(backend),
        "job_id": job.job_id(),
        "shots": shots,
        "wall_seconds": round(time.time() - t0, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "circuits": [],
    }
    try:
        out["quantum_seconds"] = job.usage()
    except Exception:
        out["quantum_seconds"] = None
    for circ, isa_c, pub in zip(circuits, isa, result, strict=True):
        creg = circ.cregs[0].name
        out["circuits"].append(
            {"name": circ.name, "counts": getattr(pub.data, creg).get_counts(), **circuit_stats(isa_c)}
        )
    return out


def save_result(result: dict, filename: str) -> str:
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / filename
    path.write_text(json.dumps(result, indent=1), encoding="utf8")
    return str(path)


def load_result(filename: str):
    path = RESULTS_DIR / filename
    return json.loads(path.read_text(encoding="utf8")) if path.exists() else None
