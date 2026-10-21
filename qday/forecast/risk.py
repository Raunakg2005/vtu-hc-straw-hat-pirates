"""Turn scanned assets into quantum-risk verdicts (break year, Mosca's inequality, harvest-now).

Mosca's inequality: if x + y > z the asset is already at risk, where
  x = how long the protected data must stay secret (shelf life, years)
  y = how long migration to post-quantum crypto will take (years)
  z = years until a quantum computer can break the algorithm
Confidentiality assets (key exchange / public-key encryption) are exposed to
"harvest now, decrypt later": traffic recorded today is readable in the break year.
Authentication assets (signatures, certificates) are only attacked after the break year,
so for them the test is y > z (can we migrate before forgery becomes possible?).
"""

from ..catalog import describe, size_parameter
from .estimates import requirements_for
from .roadmap import first_break_year, machine_at, status_in_year

CONFIDENTIALITY = {"pke", "kem", "key-agree"}

DEFAULT_SHELF_LIFE = {  # years the data must stay secret, editable in the dashboard
    "key exchange": 10,
    "public-key crypto": 10,
    "symmetric encryption": 10,
    "bulk encryption": 10,
    "key encapsulation": 10,
}


def assess_asset(asset: dict, year_now: int = 2026, migration_years: float = 3,
                 shelf_life: float = None, scenario: str = "trend", rsa_source: str = "gidney2025") -> dict:
    name = asset["algorithm"]
    info = describe(name.split(" (")[0])
    req = requirements_for(size_parameter(name), rsa_source) if info["status"] == "shor" else None
    break_year = first_break_year(req, scenario, start=year_now) if req else None
    confidentiality = info["primitive"] in CONFIDENTIALITY
    x = shelf_life if shelf_life is not None else DEFAULT_SHELF_LIFE.get(asset.get("purpose"), 10)
    y = migration_years
    z = (break_year - year_now) if break_year else None

    if info["status"] == "classical":
        level, why = "critical", "already broken classically; replace now regardless of quantum"
    elif info["status"] == "shor" and req is None:
        level, why = "high", "Shor-vulnerable; no published size estimate for this parameter"
    elif info["status"] == "shor" and z is None:
        level, why = "medium", ("Shor-vulnerable; not breakable within this scenario (IBM's published "
                                "roadmap stops at 2033), so the date is unknown, not safe")
    elif info["status"] == "shor":
        exposed = (x + y > z) if confidentiality else (y > z)
        if exposed:
            level = "critical"
            why = (f"x+y = {x:g}+{y:g} > z = {z}: data protected today is readable by {break_year}"
                   if confidentiality else f"migration ({y:g} y) slower than time to forgery ({z} y)")
        else:
            level = "high"
            why = f"breakable in {break_year} under this scenario; migrate before then"
    elif info["status"] == "grover":
        level, why = "medium", "Grover halves the key strength (128 → 64-bit effective); move to 256-bit"
    elif info["status"] == "safe":
        level, why = "safe", "no known efficient quantum attack"
    else:
        level, why = "unknown", "algorithm not in catalog; review manually"

    return {
        **asset,
        "family": info["family"],
        "primitive": info["primitive"],
        "quantum_status": info["status"],
        "replacement": info["replacement"],
        "confidentiality": confidentiality,
        "logical_qubits_needed": req["logical_qubits"] if req else None,
        "toffoli_needed": req["toffoli"] if req else None,
        "estimate_source": req["source"] if req else None,
        "break_year": break_year,
        "mosca_x": x, "mosca_y": y, "mosca_z": z,
        "risk": level,
        "why": why,
    }


def assess_all(assets, **kw):
    order = {"critical": 0, "high": 1, "medium": 2, "unknown": 3, "safe": 4}
    return sorted((assess_asset(a, **kw) for a in assets), key=lambda r: order.get(r["risk"], 9))


def timeline_status(assessed: list, year: int, scenario: str = "trend", rsa_source: str = "gidney2025"):
    """Per-asset status in a given year, for the time-machine slider."""
    out = []
    for a in assessed:
        req = requirements_for(size_parameter(a["algorithm"]), rsa_source) \
            if a["quantum_status"] == "shor" else None
        if req:
            status = status_in_year(req, year, scenario)
        else:
            status = {"grover": "weakened", "classical": "broken",
                      "shor": "vulnerable (size unknown)"}.get(a["quantum_status"], "safe")
        out.append({**a, "status_in_year": status})
    return out, machine_at(year, scenario)


def harvest_now_window(break_year, shelf_life: float, year_now: int = 2026):
    """Years whose recorded traffic is still secret-worthy when the algorithm breaks."""
    if not break_year:
        return []
    return [t for t in range(year_now, break_year + 1) if t + shelf_life > break_year]
