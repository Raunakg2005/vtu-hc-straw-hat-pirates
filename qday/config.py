"""Credentials and IBM Quantum service setup.

The API key is read from a .env file at runtime and never written into code or logs.
Lookup order for the file: $QDAY_ENV_FILE, then ./.env in the project root.
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"


def _parse_env(path: Path) -> dict:
    values = {}
    for line in path.read_text(encoding="utf8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_credentials() -> dict:
    """Return {'token', 'instance'} from the environment or a .env file (values may be None)."""
    token = os.environ.get("IBM_QUANTUM_TOKEN")
    instance = os.environ.get("IBM_QUANTUM_INSTANCE")
    candidates = [os.environ.get("QDAY_ENV_FILE"), PROJECT_ROOT / ".env"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            env = _parse_env(Path(candidate))
            token = token or env.get("IBM_QUANTUM_TOKEN") or None
            instance = instance or env.get("IBM_QUANTUM_INSTANCE") or None
            break
    return {"token": token, "instance": instance}


def runtime_service():
    """An authenticated QiskitRuntimeService (falls back to the locally saved account)."""
    from qiskit_ibm_runtime import QiskitRuntimeService

    creds = load_credentials()
    if creds["token"]:
        return QiskitRuntimeService(
            channel="ibm_quantum_platform", token=creds["token"], instance=creds["instance"]
        )
    return QiskitRuntimeService()
