from pathlib import Path

from qday.catalog import describe, size_parameter
from qday.forecast.estimates import ecc_requirements, rsa_requirements
from qday.forecast.risk import assess_asset, harvest_now_window, timeline_status
from qday.forecast.roadmap import first_break_year, machine_at, status_in_year
from qday.migrate.pqc import hybrid_key_exchange, signature_comparison
from qday.scanner.cbom import build_cbom
from qday.scanner.code import scan_code

SAMPLES = Path(__file__).resolve().parent.parent / "samples" / "legacy_app"


# ---------------------------------------------------------------- estimates (cited numbers)
def test_published_estimates():
    g25 = rsa_requirements(2048)
    assert g25["logical_qubits"] == 1399 and g25["toffoli"] == 6.5e9
    ge19 = rsa_requirements(2048, "gidney_ekera2019")
    assert 6100 < ge19["logical_qubits"] < 6300 and 2.5e9 < ge19["toffoli"] < 3e9
    assert ecc_requirements(256)["logical_qubits"] == 2330
    assert rsa_requirements(4096) is None  # Gidney 2025 only covers RSA-2048


def test_roadmap_and_qubits_ready_state():
    assert machine_at(2028)["logical_qubits"] == 0
    assert machine_at(2029)["logical_qubits"] == 200
    assert machine_at(2033, "roadmap")["logical_qubits"] == 2000
    rsa = rsa_requirements(2048)
    # Blue Jay has enough qubits for RSA-2048 but not enough operations
    assert status_in_year(rsa, 2033, "roadmap") == "qubits-ready"
    assert first_break_year(rsa, "roadmap") is None
    assert first_break_year(rsa, "trend") is not None


# ---------------------------------------------------------------- risk
def test_mosca_marks_long_lived_rsa_critical():
    r = assess_asset({"algorithm": "RSA-2048", "purpose": "public-key crypto", "location": "x"},
                     migration_years=3, shelf_life=10, scenario="trend")
    assert r["risk"] == "critical" and r["mosca_x"] + r["mosca_y"] > r["mosca_z"]


def test_safe_and_classical_assets():
    assert assess_asset({"algorithm": "X25519MLKEM768", "purpose": "key exchange", "location": "x"})["risk"] == "safe"
    assert assess_asset({"algorithm": "MD5", "purpose": "hash", "location": "x"})["risk"] == "critical"
    assert assess_asset({"algorithm": "AES-128", "purpose": "symmetric encryption", "location": "x"})["risk"] == "medium"


def test_shor_vulnerable_is_never_shown_safe():
    rows, _ = timeline_status([assess_asset({"algorithm": "ECDSA", "purpose": "signature", "location": "x"})], 2030)
    assert rows[0]["status_in_year"] != "safe"


def test_harvest_window():
    assert harvest_now_window(2037, 10, 2026) == list(range(2028, 2038))
    assert harvest_now_window(None, 10) == []


# ---------------------------------------------------------------- scanner + CBOM
def test_code_scan_finds_sample_algorithms():
    found = {a["algorithm"] for a in scan_code(str(SAMPLES))["assets"]}
    assert {"RSA-2048", "ECDSA-P-256", "ECDH-P-256", "AES-128", "MD5", "SHA-1"} <= found


def test_catalog_sizes():
    assert size_parameter("RSA-3072") == ("rsa", 3072)
    assert size_parameter("ECDSA-P-384") == ("ecc", 384)
    assert describe("ECDSA-P-256")["status"] == "shor"


def test_cbom_is_cyclonedx_16():
    assets = scan_code(str(SAMPLES))["assets"]
    bom = build_cbom(assets)
    assert bom["bomFormat"] == "CycloneDX" and bom["specVersion"] == "1.6"
    rsa = next(c for c in bom["components"] if c["name"] == "RSA-2048")
    assert rsa["type"] == "cryptographic-asset"
    assert rsa["cryptoProperties"]["algorithmProperties"]["nistQuantumSecurityLevel"] == 0


# ---------------------------------------------------------------- post-quantum migration
def test_hybrid_key_exchange():
    h = hybrid_key_exchange()
    assert h["keys_match"] and h["message_roundtrip"] and h["session_key_bits"] == 256


def test_ml_dsa_rejects_tampering():
    ml = next(r for r in signature_comparison() if r["algorithm"] == "ML-DSA-65")
    assert ml["verified"] and ml["tampered_rejected"] and ml["signature_bytes"] == 3309
