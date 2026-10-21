"""End-to-end tests of the dashboard: run the real app headlessly, use the widgets, check the output.

Uses Streamlit's AppTest. Nothing is prefilled or scanned on load; the tests scan the bundled sample
code folder so they never depend on the network.
"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def blank():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    return at


def fresh():
    """The app after the user clicked 'scan the sample app'."""
    at = blank()
    at.button(key="scan_sample").click().run()
    assert not at.exception, at.exception
    return at


def page_text(at) -> str:
    return " ".join(str(m.value) for m in at.markdown) + " " + " ".join(str(c.value) for c in at.caption)


def submit_scan(at, hosts: str, repo: str):
    at.text_area(key="hosts").set_value(hosts)
    at.text_input(key="repo").set_value(repo)
    next(b for b in at.button if "Scan now" in str(b.label)).click()
    at.run()
    assert not at.exception, at.exception
    return at


def test_nothing_is_prefilled_or_scanned_on_load():
    at = blank()
    assert at.text_area(key="hosts").value == ""
    assert at.text_input(key="repo").value == ""
    text = page_text(at)
    assert "We found" not in text and "press <b>Scan now</b>" in text
    assert "Nothing scanned yet" in text


def test_app_loads_and_scans_sample_code():
    at = fresh()
    text = page_text(at)
    assert "We found" in text and "need fixing now" in text
    assert "RSA-2048" in text and "Fix now" in text  # sample app has RSA-2048 in two places


def test_missing_folder_is_reported_not_crashing():
    at = submit_scan(fresh(), "", "Z:/definitely/not/a/folder")
    assert "folder not found" in page_text(at)
    assert "We found <b>0</b>" in page_text(at)


def test_unreachable_host_is_reported_not_crashing():
    at = submit_scan(fresh(), "no-such-host.invalid", "")
    assert "Could not scan" in page_text(at)


def test_empty_scan_still_renders_every_tab():
    at = submit_scan(fresh(), "", "")
    text = page_text(at)
    assert "We found <b>0</b>" in text
    assert "Already safe" in text and "Nothing here." in text


@pytest.mark.parametrize("year", [2026, 2033, 2050])
def test_time_machine_extremes(year):
    at = fresh()
    at.slider(key="year").set_value(year).run()
    assert not at.exception
    assert f"In <b>{year}</b>" in page_text(at)


def test_roadmap_only_scenario_has_no_break_years():
    at = fresh()
    at.radio(key="scenario").set_value("roadmap").run()
    assert not at.exception
    assert "earliest break" not in page_text(at)  # nothing breaks on the published roadmap alone


def test_alternative_rsa_estimate_and_assumptions():
    at = fresh()
    at.selectbox(key="rsa_source").set_value("gidney_ekera2019")
    at.slider(key="shelf_life").set_value(30)
    at.slider(key="migration").set_value(10).run()
    assert not at.exception


def test_shor_defaults_and_n21():
    at = fresh()
    assert "Factored <b>15 = 3 × 5</b>" in page_text(at)
    at.selectbox(key="shor_N").set_value(21).run()
    assert at.radio(key="shor_be_21").options == ["Ideal simulator"]  # noisy N = 21 is blocked
    at.button(key="run_shor").click().run()
    assert not at.exception
    assert "21 = 3 × 7" in page_text(at) or "no factor" in page_text(at)


def test_shor_trivial_base_explains_itself():
    at = fresh()
    at.selectbox(key="shor_N").set_value(21).run()
    at.selectbox(key="shor_a_21").set_value(5).run()   # 5^3 = -1 mod 21
    at.button(key="run_shor").click().run()
    assert not at.exception
    assert "known case" in page_text(at)


def test_shor_on_noisy_backend():
    at = fresh()
    at.radio(key="shor_be_15").set_value("fake_marrakesh").run()
    at.button(key="run_shor").click().run()
    assert not at.exception
    assert "noisy ibm_marrakesh copy" in page_text(at)


def test_grover_key_size_switch_with_large_secret():
    at = fresh()
    at.selectbox(key="grover_bits").set_value(4).run()
    at.number_input(key="secret_4").set_value(13).run()
    at.button(key="run_grover").click().run()
    assert not at.exception
    assert "Recovered key <b>13</b> (correct)" in page_text(at)
    at.selectbox(key="grover_bits").set_value(3).run()   # 13 must not leak into the 3-bit range
    assert not at.exception
    at.button(key="run_grover").click().run()
    assert not at.exception


def test_migrate_tab_and_rerun():
    at = fresh()
    assert "established" in page_text(at)
    at.button(key="rerun_pqc").click().run()
    assert not at.exception
    assert "rejected" in page_text(at)


@pytest.mark.parametrize("bad_host", ["-proxy evil:8080", "host;id", "ftp://example.com"])
def test_ui_rejects_injection_hosts(bad_host):
    at = submit_scan(fresh(), bad_host, "")
    assert "Could not scan" in page_text(at) and "invalid" in page_text(at) or "unsupported" in page_text(at)


def test_ui_strips_url_to_hostname():
    at = fresh()
    from qday.safety import parse_hosts
    hosts, errors = parse_hosts("https://example.com/path")
    assert hosts == ["example.com"] and not errors and not at.exception


def test_prove_tab_shows_all_validation_sections():
    text = page_text(fresh())
    for heading in ("a real IBM quantum computer", "Tested on <em", "Pre-registered rules", "Grover fingerprint"):
        assert heading in text


def test_sources_tab_cites_every_estimate():
    text = page_text(fresh())
    for needle in ("arxiv.org/abs/2505.15917", "arxiv.org/abs/1905.09749", "arxiv.org/abs/1706.06752",
                   "ibm.com/roadmaps/quantum"):
        assert needle in text


def test_cbom_download_is_offered():
    at = fresh()
    labels = [str(getattr(b, "label", "")) for b in at.get("download_button")]
    assert any("CBOM" in label for label in labels)


def test_sidebar_reset_restores_default_assumptions():
    at = fresh()
    at.slider(key="shelf_life").set_value(25).run()
    at.slider(key="migration").set_value(8).run()
    at.radio(key="scenario").set_value("roadmap").run()
    at.button(key="reset_settings").click().run()
    assert not at.exception
    assert (at.slider(key="shelf_life").value, at.slider(key="migration").value) == (10, 3)
    assert at.radio(key="scenario").value == "trend"
    assert at.selectbox(key="rsa_source").value == "gidney2025"
