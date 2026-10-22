"""docs/RESULTS.md and results/noise_calibration.json must match what the raw hardware files say."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import summarize_results  # noqa: E402


@pytest.fixture(scope="module")
def rendered():
    return summarize_results.render()


def test_results_document_is_up_to_date(rendered):
    doc, cal = rendered
    assert (ROOT / "docs" / "RESULTS.md").read_text(encoding="utf8") == doc, \
        "run: python scripts/summarize_results.py"
    assert (ROOT / "results" / "noise_calibration.json").read_text(encoding="utf8") == cal


def test_every_hardware_job_id_is_listed(rendered):
    doc, _ = rendered
    ids = [json.loads((ROOT / "results" / f).read_text(encoding="utf8"))["job_id"]
           for f in ("hardware_run.json", "suite_job_ibm_fez.json", "suite_job_ibm_kingston.json",
                     "suite_job_ibm_marrakesh.json")]
    ids += [json.loads(p.read_text(encoding="utf8"))["job_id"] for p in (ROOT / "results" / "strict").glob("ibm_*.json")]
    assert len(ids) == 8
    for job_id in ids:
        assert f"`{job_id}`" in doc


def test_qpu_seconds_add_up(rendered):
    _, cal = rendered
    assert json.loads(cal)["qpu_seconds_total"] == 8 + 3 * 21 + 4 * 23


def test_check_mode_passes_on_the_committed_files(capsys):
    summarize_results.main(["--check"])
    assert "up to date" in capsys.readouterr().out
