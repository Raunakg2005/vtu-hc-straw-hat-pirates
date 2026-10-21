"""Build a CycloneDX 1.6 Cryptography Bill of Materials (CBOM) from scan assets."""

import uuid
from collections import defaultdict
from datetime import datetime, timezone

from .. import __version__
from ..catalog import CURVE_BITS, describe, size_parameter


def _algorithm_properties(name: str, info: dict) -> dict:
    props = {"primitive": info["primitive"], "nistQuantumSecurityLevel": info["nist_quantum_level"]
             if info["nist_quantum_level"] is not None else 0}
    size = size_parameter(name)
    if size and size[0] == "rsa":
        props["parameterSetIdentifier"] = str(size[1])
    for curve in CURVE_BITS:
        if curve.upper() in name.upper():
            props["curve"] = curve
    return props


def build_cbom(assets: list, target: str = "scan") -> dict:
    grouped = defaultdict(list)
    for a in assets:
        grouped[a["algorithm"]].append(a)
    components = []
    for name, items in sorted(grouped.items()):
        info = describe(name)
        components.append({
            "type": "cryptographic-asset",
            "bom-ref": f"crypto/{name}",
            "name": name,
            "cryptoProperties": {
                "assetType": "algorithm",
                "algorithmProperties": _algorithm_properties(name, info),
            },
            "properties": [
                {"name": "qday:quantum-status", "value": info["status"]},
                {"name": "qday:recommended-replacement", "value": info["replacement"] or "none needed"},
                {"name": "qday:purposes", "value": "; ".join(sorted({i["purpose"] for i in items}))},
            ],
            "evidence": {"occurrences": [{"location": i["location"]} for i in items[:50]]},
        })
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tools": {"components": [{"type": "application", "name": "q-day-time-machine",
                                       "version": __version__}]},
            "component": {"type": "application", "name": target},
        },
        "components": components,
    }
