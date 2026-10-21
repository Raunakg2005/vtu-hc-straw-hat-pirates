"""Performance budgets: the tool must stay usable on real-size inputs."""

import time

import pytest

from qday.forecast.risk import assess_all, timeline_status
from qday.scanner.cbom import build_cbom
from qday.scanner.code import scan_code

LINES = ["key = rsa.generate_private_key(public_exponent=65537, key_size=2048)", "h = hashlib.md5(x)",
         "x = 1", "import os", "k = ec.generate_private_key(ec.SECP256R1())", "y = AESGCM.generate_key(bit_length=128)"]


@pytest.fixture(scope="module")
def big_repo(tmp_path_factory):
    root = tmp_path_factory.mktemp("repo")
    for i in range(1500):
        d = root / f"pkg{i % 30}"
        d.mkdir(exist_ok=True)
        (d / f"m{i}.py").write_text("\n".join(LINES * 5) + "\n", encoding="utf8")
    return root


def timed(fn, *a, **kw):
    t0 = time.perf_counter()
    out = fn(*a, **kw)
    return out, time.perf_counter() - t0


def test_scan_1500_files_under_15_seconds(big_repo):
    res, secs = timed(scan_code, str(big_repo), max_findings=100_000)
    assert res["files_scanned"] == 1500 and secs < 15


def test_assess_10000_assets_under_3_seconds():
    assets = [{"algorithm": a, "purpose": "x", "location": f"f{i}"}
              for i, a in enumerate(["RSA-2048", "ECDSA-P-256", "AES-128", "MD5", "X25519MLKEM768"] * 2000)]
    res, secs = timed(assess_all, assets)
    assert len(res) == 10_000 and secs < 3


def test_timeline_for_every_year_under_2_seconds():
    assessed = assess_all([{"algorithm": a, "purpose": "x", "location": "f"}
                           for a in ["RSA-2048", "RSA-4096", "ECDSA-P-384"] * 50])
    _, secs = timed(lambda: [timeline_status(assessed, y) for y in range(2026, 2051)])
    assert secs < 2


def test_cbom_for_10000_assets_under_2_seconds():
    assets = [{"algorithm": f"RSA-{2048 + (i % 3) * 1024}", "purpose": "x", "location": f"f{i}"} for i in range(10_000)]
    bom, secs = timed(build_cbom, assets)
    assert len(bom["components"]) == 3 and secs < 2
