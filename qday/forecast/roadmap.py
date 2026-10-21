"""IBM's public fault-tolerant roadmap and simple scenarios built on it.

IBM targets (https://www.ibm.com/roadmaps/quantum/, stated as current intent):
  Starling (2029): first fault-tolerant system, 200 (logical) qubits, 100 million gates
  Blue Jay (2033+): 2,000-qubit fault-tolerant system, 1 billion gates
  (Starling's 200 logical qubits are confirmed in IBM's blog "How IBM will build the world's
  first large-scale, fault-tolerant quantum computer", 10 June 2025; Blue Jay's 2,000 qubits
  are treated as logical because it is the fault-tolerant successor.)
Beyond 2033 nothing is published; the "trend" scenario continues the Starling -> Blue Jay
growth rate (x10 in 4 years), clearly labelled as a hypothetical extrapolation.

Comparing a Toffoli count with IBM's "operations" is attacker-friendly (one Toffoli costs
several logical operations), so break years here are, if anything, early: a cautious view.
"""

ROADMAP = [
    {"name": "Starling", "year": 2029, "logical_qubits": 200, "operations": 1e8},
    {"name": "Blue Jay", "year": 2033, "logical_qubits": 2000, "operations": 1e9},
]
ROADMAP_SOURCES = ["https://www.ibm.com/roadmaps/quantum/",
                   "https://www.ibm.com/quantum/blog/large-scale-ftqc"]

TREND_GROWTH = (ROADMAP[1]["logical_qubits"] / ROADMAP[0]["logical_qubits"]) ** (
    1 / (ROADMAP[1]["year"] - ROADMAP[0]["year"]))  # ~1.78x per year

SCENARIOS = {
    "roadmap": "IBM published roadmap only (no extrapolation after 2033)",
    "trend": "Roadmap, then the Starling→Blue Jay growth rate continues (hypothetical)",
}


def machine_at(year: int, scenario: str = "trend", growth: float = TREND_GROWTH) -> dict:
    """Best fault-tolerant machine available in a given year under a scenario."""
    current = {"name": "no fault-tolerant machine", "logical_qubits": 0, "operations": 0.0}
    for m in ROADMAP:
        if year >= m["year"]:
            current = dict(m)
    last = ROADMAP[-1]
    if scenario == "trend" and year > last["year"]:
        k = growth ** (year - last["year"])
        current = {"name": f"extrapolated ({year})", "year": year,
                   "logical_qubits": round(last["logical_qubits"] * k),
                   "operations": last["operations"] * k}
    return current


def status_in_year(req: dict, year: int, scenario: str = "trend") -> str:
    """'safe' | 'qubits-ready' (enough qubits, not enough operations) | 'breakable'."""
    if not req:
        return "safe"
    m = machine_at(year, scenario)
    qubits_ok = m["logical_qubits"] >= req["logical_qubits"]
    ops_ok = m["operations"] >= req["toffoli"]
    if qubits_ok and ops_ok:
        return "breakable"
    if qubits_ok:
        return "qubits-ready"
    return "safe"


def first_break_year(req: dict, scenario: str = "trend", start: int = 2026, horizon: int = 2060):
    if not req:
        return None
    for year in range(start, horizon + 1):
        if status_in_year(req, year, scenario) == "breakable":
            return year
    return None
