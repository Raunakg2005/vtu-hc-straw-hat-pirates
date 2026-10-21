"""The `qday` command-line tool: outputs, exit codes and input errors."""

import json
from pathlib import Path

import pytest

from qday.cli import build_parser, main

SAMPLE = str(Path(__file__).resolve().parent.parent / "samples" / "legacy_app")


def run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_scan_json_lists_findings(capsys):
    code, out, _ = run(capsys, "scan", "--path", SAMPLE, "--json")
    data = json.loads(out)
    assert code == 0 and {a["algorithm"] for a in data["assets"]} >= {"RSA-2048", "MD5"}


@pytest.mark.parametrize("level,expected", [("critical", 1), ("high", 1), ("medium", 1)])
def test_fail_on_vulnerable_sample(capsys, level, expected):
    assert run(capsys, "scan", "--path", SAMPLE, "--fail-on", level)[0] == expected


def test_fail_on_clean_code_passes(capsys, tmp_path):
    (tmp_path / "ok.py").write_text("key = AESGCM.generate_key(bit_length=256)\n", encoding="utf8")
    assert run(capsys, "scan", "--path", str(tmp_path), "--fail-on", "medium")[0] == 0


@pytest.mark.parametrize("host", ["-proxy evil:8080", "a b", "host;id"])
def test_scan_rejects_injection_and_exits_2(capsys, host):
    code, _, err = run(capsys, "scan", "--host", host)
    assert code == 2 and "nothing to scan" in err


def test_scan_missing_folder_exits_2(capsys, tmp_path):
    assert run(capsys, "scan", "--path", str(tmp_path / "nope"))[0] == 2


def test_cbom_to_file(capsys, tmp_path):
    out = tmp_path / "cbom.json"
    code, stdout, _ = run(capsys, "cbom", "--path", SAMPLE, "-o", str(out))
    bom = json.loads(out.read_text(encoding="utf8"))
    assert code == 0 and bom["specVersion"] == "1.6" and "wrote" in stdout


def test_cbom_to_stdout(capsys):
    code, out, _ = run(capsys, "cbom", "--path", SAMPLE)
    assert code == 0 and json.loads(out)["bomFormat"] == "CycloneDX"


@pytest.mark.parametrize("alg,year", [("RSA-2048", 2037), ("ECDSA-P-256", 2042)])
def test_forecast(capsys, alg, year):
    code, out, _ = run(capsys, "forecast", alg)
    assert code == 0 and json.loads(out)["first_break_year"] == year


def test_forecast_roadmap_only_never_breaks(capsys):
    code, out, _ = run(capsys, "forecast", "RSA-2048", "--scenario", "roadmap")
    assert code == 0 and json.loads(out)["first_break_year"] is None


@pytest.mark.parametrize("alg", ["AES-256", "ML-KEM-768", "nonsense"])
def test_forecast_unsupported_exits_2(capsys, alg):
    assert run(capsys, "forecast", alg)[0] == 2


def test_shor(capsys):
    code, out, _ = run(capsys, "shor", "--N", "15", "--a", "7", "--shots", "1000")
    assert code == 0 and json.loads(out)["factors"] == [3, 5]


def test_shor_bad_base_exits_2(capsys):
    assert run(capsys, "shor", "--N", "15", "--a", "5")[0] == 2


def test_grover(capsys):
    code, out, _ = run(capsys, "grover", "--bits", "3", "--secret", "6", "--shots", "1000")
    assert code == 0 and json.loads(out)["recovered_key"] == 6


@pytest.mark.parametrize("secret", ["8", "-1", "100"])
def test_grover_secret_out_of_range_exits_2(capsys, secret):
    assert run(capsys, "grover", "--bits", "3", "--secret", secret)[0] == 2


def test_pqc(capsys):
    code, out, _ = run(capsys, "pqc")
    assert code == 0 and json.loads(out)["keys_match"]


@pytest.mark.parametrize("argv", [[], ["unknown"], ["shor", "--N", "33"], ["grover", "--bits", "9"]])
def test_bad_arguments_exit_nonzero(argv):
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(argv)
    assert exc.value.code != 0
