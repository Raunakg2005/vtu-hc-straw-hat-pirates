"""Golden tests: every claim in the README / dashboard is recomputed from the raw hardware counts.

If someone edits a result file, changes the analysis, or the README drifts from the data, these fail.
"""

import json
from pathlib import Path

import pytest

from qday.quantum import grover, shor
from qday.quantum.stats import summarise

RESULTS = Path(__file__).resolve().parent.parent / "results"


def load(name):
    path = RESULTS / name
    if not path.exists():
        pytest.skip(f"{name} not present")
    return json.loads(path.read_text(encoding="utf8"))


# ---------------------------------------------------------------- first hardware run (ibm_marrakesh)
def test_first_run_metadata():
    d = load("hardware_run.json")
    assert d["backend"] == "ibm_marrakesh" and d["hardware"] and d["shots"] == 4000


@pytest.mark.parametrize("a,expected_rate", [(7, 0.682), (2, 0.682), (13, 0.716)])
def test_first_run_shor_claims(a, expected_rate):
    d = load("hardware_run.json")
    c = next(c for c in d["circuits"] if c["name"] == f"shor_N15_a{a}")
    r = shor.analyse_counts(c["counts"], a, 15, 3)
    assert r["factors"] == (3, 5) and r["most_likely_order"] == 4
    assert r["success_probability"] == pytest.approx(expected_rate, abs=5e-4)
    top4 = {int(o["y"]) for o in r["outcomes"][:4]}
    assert top4 == {0, 2, 4, 6}  # README: the four most frequent outcomes are the ideal peaks


@pytest.mark.parametrize("it,expected", [(1, 0.545), (2, 0.463)])
def test_first_run_grover_claims(it, expected):
    d = load("hardware_run.json")
    c = next(c for c in d["circuits"] if c["name"].endswith(f"_it{it}"))
    m = grover.parse_name(c["name"])
    r = grover.analyse_counts(c["counts"], m["plaintext"], m["ciphertext"], it, 3)
    assert r["recovered_key"] == 6 and r["success_probability"] == pytest.approx(expected, abs=5e-4)


# ---------------------------------------------------------------- 3-backend suite
@pytest.mark.parametrize("backend", ["ibm_fez", "ibm_kingston", "ibm_marrakesh"])
def test_suite_all_45_pass(backend):
    run = load("hardware_suite.json")["runs"][backend]
    tests = [r for r in run["rows"] if not r["control"]]
    assert len(tests) == 15 and all(r["significant"] for r in tests)


@pytest.mark.parametrize("backend", ["ibm_fez", "ibm_kingston", "ibm_marrakesh"])
def test_suite_controls(backend):
    run = load("hardware_suite.json")["runs"][backend]
    for r in (r for r in run["rows"] if r["control"]):
        if r["kind"] == "shor":
            assert r["successes"] == 0
        else:
            assert r["ci95"][0] <= r["baseline"] <= r["ci95"][1]


@pytest.mark.parametrize("backend", ["ibm_fez", "ibm_kingston", "ibm_marrakesh"])
def test_suite_rows_are_internally_consistent(backend):
    for r in load("hardware_suite.json")["runs"][backend]["rows"]:
        s = summarise(r["successes"], r["shots"], r["baseline"])
        assert s["rate"] == pytest.approx(r["rate"]) and s["significant"] == r["significant"]


def test_suite_max_p_value_claim():
    runs = load("hardware_suite.json")["runs"]
    worst = max(r["p_value"] for be in ("ibm_fez", "ibm_kingston", "ibm_marrakesh")
                for r in runs[be]["rows"] if not r["control"])
    assert worst == pytest.approx(7.5e-220, rel=0.05)  # README: largest p-value 7.5 x 10^-220


# ---------------------------------------------------------------- strict validation
@pytest.mark.parametrize("backend,passed", [("ibm_kingston", 14), ("ibm_fez", 11), ("ibm_marrakesh", 9)])
def test_strict_headline(backend, passed):
    b = load("hardware_strict.json")["backends"][backend]
    assert b["summary"]["tests_passed"] == passed and b["summary"]["tests"] == 14


def test_strict_shor_and_grover_totals():
    backends = load("hardware_strict.json")["backends"]
    rows = [r for be, b in backends.items() if b["hardware"] for r in b["rows"] if not r["control"]]
    shor_rows = [r for r in rows if r["test"].startswith("Shor")]
    grover_rows = [r for r in rows if r["test"].startswith("Grover")]
    assert (sum(r["pass"] for r in shor_rows), len(shor_rows)) == (24, 24)
    assert (sum(r["pass"] for r in grover_rows), len(grover_rows)) == (10, 18)
    assert all(r["criteria"]["C1"]["pass"] for r in rows)  # README: C1 passed 42 / 42


@pytest.mark.parametrize("backend", ["ibm_kingston", "ibm_fez", "ibm_marrakesh"])
def test_strict_fingerprint_passes_everywhere(backend):
    assert load("hardware_strict.json")["backends"][backend]["C4_fingerprint"]["pass"]


def test_strict_repeatability_claim():
    c6 = load("hardware_strict.json")["backends"]["ibm_kingston"]["C6_repeatability"]
    assert c6["pass"] and c6["n_pass"] == c6["n"] == 19


def test_strict_marrakesh_placement_claim():
    rows = load("hardware_strict.json")["backends"]["ibm_marrakesh"]["rows"]
    g = {r["layout"]: r for r in rows if r["test"].startswith("Grover") and r["test"].endswith("it=2")
         and not r["control"] and r["layout"] != "auto"}
    assert g["region-2"]["pass"] and g["region-2"]["rate"] == pytest.approx(0.643, abs=5e-4)


def test_strict_bonferroni_denominator():
    d = load("hardware_strict.json")
    assert d["m_tests"] == 42 and d["criteria"] == "strict-v1"
