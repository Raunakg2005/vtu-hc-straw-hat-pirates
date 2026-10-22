"""Catalog, published estimates, roadmap engine and Mosca risk logic."""

from math import ceil, log2

import pytest
from hypothesis import given
from hypothesis import strategies as st

from qday.catalog import ALGORITHMS, describe, family_of, size_parameter
from qday.forecast import estimates, roadmap
from qday.forecast.risk import assess_all, assess_asset, harvest_now_window

# ---------------------------------------------------------------- catalog
STATUS = [
    ("RSA-2048", "shor"), ("RSA-4096", "shor"), ("ECDSA-P-256", "shor"), ("ECDSA-P-521", "shor"),
    ("EdDSA-Ed25519", "shor"), ("ECDH-P-384", "shor"), ("X25519", "shor"), ("X448", "shor"), ("DH", "shor"),
    ("DSA", "shor"), ("ML-KEM-768", "safe"), ("ML-KEM-1024", "safe"), ("X25519MLKEM768", "safe"),
    ("ML-DSA-65", "safe"), ("SLH-DSA", "safe"), ("AES-128", "grover"), ("AES-128-GCM", "grover"),
    ("AES-256", "safe"), ("AES-256-GCM", "safe"), ("AES-192", "safe"), ("ChaCha20-Poly1305", "safe"),
    ("SHA-256", "safe"), ("SHA-384", "safe"), ("SHA3", "safe"), ("MD5", "classical"), ("SHA-1", "classical"),
    ("DES", "classical"), ("3DES", "classical"), ("RC4", "classical"), ("SomethingNew", "unknown"),
]


@pytest.mark.parametrize("name,status", STATUS)
def test_quantum_status(name, status):
    assert describe(name)["status"] == status


@pytest.mark.parametrize("family", sorted(ALGORITHMS))
def test_every_vulnerable_family_has_a_replacement(family):
    info = ALGORITHMS[family]
    if info["status"] in ("shor", "classical", "grover"):
        assert info["replacement"]
    else:
        assert info["replacement"] is None


@pytest.mark.parametrize("name,level", [("RSA-2048", 0), ("ECDSA-P-256", 0), ("AES-128", 1), ("AES-256", 5),
                                        ("ML-KEM-768", 3), ("ML-KEM-1024", 5), ("ML-DSA-65", 3),
                                        ("X25519MLKEM768", 3), ("ChaCha20-Poly1305", 5)])
def test_nist_quantum_level(name, level):
    assert describe(name)["nist_quantum_level"] == level


@pytest.mark.parametrize("name,expected", [
    ("RSA-2048", ("rsa", 2048)), ("RSA-3072", ("rsa", 3072)), ("RSA-15360", ("rsa", 15360)),
    ("ECDSA-P-256", ("ecc", 256)), ("ECDSA-P-384", ("ecc", 384)), ("ECDH-P-521", ("ecc", 521)),
    ("X25519", ("ecc", 255)), ("EdDSA-Ed25519", ("ecc", 255)), ("AES-256", None), ("ML-KEM-768", None),
])
def test_size_parameter(name, expected):
    assert size_parameter(name) == expected


@pytest.mark.parametrize("name,family", [("ECDSA-P-256", "ECDSA"), ("X25519MLKEM768", "X25519MLKEM768"),
                                         ("X25519", "X25519"), ("ML-KEM-768", "ML-KEM"), ("AES-256-GCM", "AES-256")])
def test_family_prefers_longest_match(name, family):
    assert family_of(name) == family


# ---------------------------------------------------------------- published estimates (exact paper values)
def test_gidney_2025_values():
    r = estimates.rsa_requirements(2048, "gidney2025")
    assert (r["logical_qubits"], r["toffoli"], r["physical_qubits"]) == (1399, 6.5e9, 1_000_000)


def test_gidney_ekera_2019_formula():
    r = estimates.rsa_requirements(2048, "gidney_ekera2019")
    assert r["logical_qubits"] == round(3 * 2048 + 0.002 * 2048 * 11)
    assert r["toffoli"] == pytest.approx(0.3 * 2048**3 + 0.0005 * 2048**3 * 11)


@pytest.mark.parametrize("n", [192, 224, 255, 256, 384, 521])
def test_roetteler_formula(n):
    r = estimates.ecc_requirements(n)
    assert r["logical_qubits"] == 9 * n + 2 * ceil(log2(n)) + 10
    assert r["toffoli"] == pytest.approx(448 * n**3 * log2(n) + 4090 * n**3)


def test_p256_matches_paper_headline():
    assert estimates.ecc_requirements(256)["logical_qubits"] == 2330


@pytest.mark.parametrize("bits", [1024, 3072, 4096])
def test_gidney_2025_falls_back_to_formula_for_other_sizes(bits):
    assert estimates.rsa_requirements(bits, "gidney2025") is None
    assert estimates.requirements_for(("rsa", bits), "gidney2025")["source"] == "gidney_ekera2019"


def test_unknown_source_rejected():
    with pytest.raises(ValueError):
        estimates.rsa_requirements(2048, "made_up")


@given(st.integers(512, 16384), st.integers(1, 4096))
def test_rsa_cost_never_decreases_with_key_size(bits, extra):
    a = estimates.rsa_requirements(bits, "gidney_ekera2019")
    b = estimates.rsa_requirements(bits + extra, "gidney_ekera2019")
    assert b["logical_qubits"] >= a["logical_qubits"] and b["toffoli"] > a["toffoli"]


@given(st.integers(160, 1024), st.integers(1, 512))
def test_ecc_cost_never_decreases_with_curve_size(bits, extra):
    a, b = estimates.ecc_requirements(bits), estimates.ecc_requirements(bits + extra)
    assert b["logical_qubits"] >= a["logical_qubits"] and b["toffoli"] > a["toffoli"]


# ---------------------------------------------------------------- roadmap engine
@pytest.mark.parametrize("year", range(2026, 2051))
@pytest.mark.parametrize("scenario", ["roadmap", "trend"])
def test_machine_by_year(year, scenario):
    m = roadmap.machine_at(year, scenario)
    if year < 2029:
        assert m["logical_qubits"] == 0
    elif year < 2033:
        assert (m["logical_qubits"], m["operations"]) == (200, 1e8)
    elif scenario == "roadmap" or year == 2033:
        assert (m["logical_qubits"], m["operations"]) == (2000, 1e9)
    else:
        assert m["logical_qubits"] > 2000 and m["operations"] > 1e9
    nxt = roadmap.machine_at(year + 1, scenario)
    assert nxt["logical_qubits"] >= m["logical_qubits"] and nxt["operations"] >= m["operations"]


@given(st.integers(1, 10**4), st.floats(1, 1e13), st.integers(1, 10**4), st.floats(1, 1e13))
def test_bigger_requirements_never_break_earlier(q1, t1, dq, dt):
    small = {"logical_qubits": q1, "toffoli": t1}
    big = {"logical_qubits": q1 + dq, "toffoli": t1 + dt}
    y_small, y_big = roadmap.first_break_year(small), roadmap.first_break_year(big)
    if y_big is not None:
        assert y_small is not None and y_small <= y_big


@pytest.mark.parametrize("req,year,status", [
    ({"logical_qubits": 100, "toffoli": 1e7}, 2028, "safe"),
    ({"logical_qubits": 100, "toffoli": 1e7}, 2029, "breakable"),
    ({"logical_qubits": 1399, "toffoli": 6.5e9}, 2033, "qubits-ready"),
    ({"logical_qubits": 2330, "toffoli": 1.3e11}, 2033, "safe"),
    (None, 2040, "safe"),
])
def test_status_in_year(req, year, status):
    assert roadmap.status_in_year(req, year, "roadmap") == status


def test_rsa2048_never_breaks_on_published_roadmap_alone():
    assert roadmap.first_break_year(estimates.rsa_requirements(2048), "roadmap") is None


# ---------------------------------------------------------------- Mosca's inequality, full truth table
GRID = [(x, y, brk) for x in (1, 5, 10, 25) for y in (1, 3, 8) for brk in (2030, 2037, 2045)]


@pytest.mark.parametrize("x,y,break_year", GRID)
def test_mosca_truth_table(monkeypatch, x, y, break_year):
    import qday.forecast.risk as risk
    monkeypatch.setattr(risk, "first_break_year", lambda req, scenario, start: break_year)
    z = break_year - 2026
    conf = assess_asset({"algorithm": "RSA-2048", "purpose": "public-key crypto", "location": "f"},
                        year_now=2026, migration_years=y, shelf_life=x)
    sig = assess_asset({"algorithm": "ECDSA-P-256", "purpose": "signature", "location": "f"},
                       year_now=2026, migration_years=y, shelf_life=x)
    assert conf["risk"] == ("critical" if x + y > z else "high")   # harvest-now applies to secrecy
    assert sig["risk"] == ("critical" if y > z else "high")       # forgery only after the break


@pytest.mark.parametrize("break_year,shelf,expected", [
    (2037, 10, list(range(2028, 2038))), (2037, 1, [2037]), (2030, 30, list(range(2026, 2031))), (None, 10, []),
])
def test_harvest_window(break_year, shelf, expected):
    assert harvest_now_window(break_year, shelf, 2026) == expected


@given(st.integers(2026, 2060), st.integers(1, 40))
def test_harvest_window_properties(break_year, shelf):
    window = harvest_now_window(break_year, shelf, 2026)
    assert all(2026 <= t <= break_year and t + shelf > break_year for t in window)


def test_assess_all_sorts_by_severity():
    assets = [{"algorithm": a, "purpose": "x", "location": "y"} for a in ("AES-256", "MD5", "AES-128", "RSA-2048")]
    order = [r["risk"] for r in assess_all(assets)]
    rank = {"critical": 0, "high": 1, "medium": 2, "unknown": 3, "safe": 4}
    assert order == sorted(order, key=rank.get)
