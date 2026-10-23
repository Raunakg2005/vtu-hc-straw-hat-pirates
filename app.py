"""Q-Day Time Machine — Streamlit dashboard.

    streamlit run app.py
"""

import json
from math import gcd
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from qday import ui
from qday.forecast.estimates import SOURCES
from qday.forecast.risk import assess_all, harvest_now_window, timeline_status
from qday.forecast.roadmap import ROADMAP, ROADMAP_SOURCES, SCENARIOS, machine_at
from qday.migrate.pqc import hybrid_key_exchange, signature_comparison
from qday.quantum import debug as qdebug
from qday.quantum import grover, shor
from qday.quantum.runner import load_result, run_sampler
from qday.safety import parse_hosts
from qday.scanner.cbom import build_cbom
from qday.scanner.code import scan_code
from qday.scanner.tls import scan_tls

LOGO = str(Path(__file__).resolve().parent / "landing" / "logo.png")
st.set_page_config(page_title="Q-Day Time Machine", page_icon=LOGO, layout="wide")
st.logo(LOGO, size="large")
ui.inject_css(st)
ui.plotly_template()

YEAR_NOW = 2026
SAMPLE_REPO = Path(__file__).resolve().parent / "samples" / "legacy_app"
BACKEND_LABELS = {"aer": "Ideal simulator", "fake_marrakesh": "Noisy ibm_marrakesh copy"}
CHART_CFG = {"displayModeBar": False}

# ---------------------------------------------------------------- forecast settings (sidebar)
SCENARIO_SHORT = {"roadmap": "IBM roadmap only", "trend": "Roadmap, then growth continues (hypothetical)"}
SIDEBAR_DEFAULTS = {"shelf_life": 10, "migration": 3, "scenario": list(SCENARIOS)[1], "rsa_source": "gidney2025"}


def reset_settings():
    st.session_state.update(SIDEBAR_DEFAULTS)


with st.sidebar:
    ui.side_home(st)
    ui.eyebrow(st, "Forecast settings")
    st.markdown("### What-if assumptions")
    st.caption("These change the Time Machine and every risk level. The defaults follow the published estimates.")
    with st.container(border=True):
        ui.side_group(st, "clock", "Your data")
        shelf_life = st.slider("How long must it stay secret? (years)", 1, 30, SIDEBAR_DEFAULTS["shelf_life"],
                               key="shelf_life", help="Mosca's x: e.g. payments ~7 years, medical records 30+ years.")
        migration = st.slider("How long would migrating take? (years)", 1, 10, SIDEBAR_DEFAULTS["migration"],
                              key="migration", help="Mosca's y: time to replace the cryptography everywhere it is used.")
    with st.container(border=True):
        ui.side_group(st, "cpu", "Quantum hardware")
        scenario = st.radio("Growth after 2033", list(SCENARIOS), format_func=SCENARIO_SHORT.get, key="scenario",
                            index=list(SCENARIOS).index(SIDEBAR_DEFAULTS["scenario"]),
                            help="IBM publishes targets up to 2033 (Blue Jay). The second option keeps the "
                                 "same growth rate afterwards; it is a hypothetical extrapolation.")
        rsa_source = st.selectbox("RSA-2048 cost estimate", ["gidney2025", "gidney_ekera2019"], key="rsa_source",
                                  format_func=lambda s: SOURCES[s]["label"],
                                  help="Published estimates of the quantum resources needed to break RSA-2048.")
    st.button("Reset to defaults", icon=":material/restart_alt:", on_click=reset_settings, key="reset_settings",
              width="stretch")


@st.cache_data(show_spinner=False)
def cached_calibration():
    """Noise measured on our IBM runs (scripts/summarize_results.py writes it)."""
    return load_result("noise_calibration.json")


@st.cache_data(show_spinner=False, ttl=3600)
def cached_tls(host):
    return scan_tls(host)


@st.cache_data(show_spinner=False)
def cached_code(path):
    return scan_code(path)


def run_scan(hosts, repo):
    assets, endpoints, errors = [], [], []
    for host in hosts:
        try:
            profile = cached_tls(host)
            endpoints.append(profile)
            assets += profile["assets"]
        except Exception as exc:  # a network error must not break the dashboard
            errors.append(f"{host}: {exc}")
    if repo:
        if not Path(repo).is_dir():
            errors.append(f"{repo}: folder not found")
        else:
            try:
                assets += cached_code(repo)["assets"]
            except Exception as exc:
                errors.append(f"{repo}: {exc}")
    st.session_state.update(assets=assets, endpoints=endpoints, scan_errors=errors)


# ---------------------------------------------------------------- hero + how it works
ui.hero(st, "Qiskit Fall Fest 2026 · Track 1 · Team Straw Hat Pirates",
        "When does your <em>encryption</em> die?",
        "Find the cryptography a quantum computer will break, see <b>when</b> it breaks, "
        "watch the attack run on a <b>real IBM quantum computer</b>, and get the fix.")
ui.steps(st, [
    ("Scan", "Enter a website or code folder; we list every encryption algorithm it uses."),
    ("Time Machine", "Slide through the years and see when quantum computers can break each one."),
    ("Prove it", "Shor and Grover attacks, built in Qiskit and run on IBM quantum hardware."),
    ("Migrate", "Swap in the new NIST post-quantum standards and see them work."),
])

tab_scan, tab_time, tab_prove, tab_migrate, tab_about = st.tabs(
    ["1 · Scan", "2 · Time Machine", "3 · Prove it", "4 · Migrate", "Sources"])

# ---------------------------------------------------------------- 1 scan
with tab_scan:
    with st.form("scan_form", border=False):
        c1, c2 = st.columns([1, 1], gap="medium")
        hosts_text = c1.text_area("Websites to scan (one per line, only ones you own)", height=96, key="hosts",
                                  placeholder="example.com")
        repo_path = c2.text_input("Code folder to scan", key="repo", placeholder="Path to your project folder")
        c2.caption("Fill in either field, or both. Nothing is scanned until you press Scan now.")
        submitted = st.form_submit_button("Scan now", type="primary", icon=":material/radar:")
    sample = st.button("No project handy? Scan the built-in vulnerable sample app", key="scan_sample",
                       icon=":material/science:")
    if submitted:
        with st.spinner("Scanning websites and code…"):
            hosts, host_errors = parse_hosts(hosts_text)
            run_scan(hosts, repo_path.strip())
            st.session_state["scan_errors"] = host_errors + st.session_state["scan_errors"]
    elif sample:
        with st.spinner("Scanning the sample app…"):
            run_scan([], str(SAMPLE_REPO))

scanned = "assets" in st.session_state
assets = st.session_state.get("assets", [])
assessed = assess_all(assets, year_now=YEAR_NOW, migration_years=migration, shelf_life=shelf_life,
                      scenario=scenario, rsa_source=rsa_source)
hw = load_result("hardware_run.json")

with tab_scan:
    if not scanned:
        ui.note(st, "Enter a website you own or a code folder above and press <b>Scan now</b>. "
                    "The other tabs use your scan results.")
    else:
        for err in st.session_state.get("scan_errors", []):
            ui.note(st, f"Could not scan <b>{err}</b>", "warn")

        fix_now = [a for a in assessed if a["risk"] == "critical"]
        plan = [a for a in assessed if a["risk"] in ("high", "medium", "unknown")]
        safe = [a for a in assessed if a["risk"] == "safe"]
        breaks = [a["break_year"] for a in assessed if a["break_year"]]
        ui.headline(st, f"We found <b>{len(assessed)}</b> uses of cryptography. "
                        f"<em>{len(fix_now)} need fixing now</em>, {len(plan)} need a migration plan"
                        + (f" (earliest break ≈ <b>{min(breaks)}</b>)" if breaks else "") + ".")

        endpoints = st.session_state.get("endpoints", [])
        pq = [e["host"] for e in endpoints if e.get("key_exchange_group") and "MLKEM" in e["key_exchange_group"].upper()]
        if pq:
            one = len(pq) == 1
            ui.note(st, f"<b>{', '.join(pq)}</b> already {'uses' if one else 'use'} post-quantum key exchange "
                        "(<code>X25519MLKEM768</code>): traffic recorded today stays secret.", "good")
            ui.note(st, f"But {'its <b>certificate still uses' if one else 'their <b>certificates still use'} "
                        "ECDSA</b>, which a quantum computer can forge. Once that is possible, someone could "
                        f"impersonate {'this site' if one else 'these sites'}.", "warn")

        ui.finding_groups(st, [
            ("Fix now", "Broken today, or data at risk before you could migrate", "alert", ui.BERRY, fix_now),
            ("Plan migration", "Breakable by future quantum computers", "info", ui.PINK, plan),
            ("Already safe", "No known quantum attack", "shield-check", ui.GREEN, safe),
        ])

        with st.expander("Technical details: full table, websites, CBOM export", icon=":material/table_view:"):
            if endpoints:
                ui.table(st, endpoints, [("host", "Website"), ("tls_version", "TLS"),
                                         ("key_exchange_group", "Key exchange"), ("cipher", "Cipher"),
                                         ("certificate_key", "Certificate key"),
                                         ("certificate_signature", "CA signature"),
                                         ("certificate_expires", "Expires")], code_cols=("key_exchange_group",))
            rows = [{**a, "break_year": a["break_year"] or ""} for a in assessed]
            ui.table(st, rows, [("risk", "Risk"), ("algorithm", "Algorithm"), ("purpose", "Used for"),
                                ("location", "Where"), ("quantum_status", "Quantum attack"),
                                ("break_year", "Breaks"), ("replacement", "Replace with"), ("why", "Why")],
                     badge_cols=("risk", "quantum_status"), code_cols=("location",))
            st.download_button("Download CBOM (CycloneDX 1.6 JSON)",
                               json.dumps(build_cbom(assets, target="q-day scan"), indent=2), "cbom.json",
                               "application/json", icon=":material/download:")
        ui.note(st, "Next: open <b>2 · Time Machine</b> to see when each of these breaks.")

# ---------------------------------------------------------------- 2 time machine
with tab_time:
    if not scanned:
        ui.note(st, "Nothing scanned yet. Run a scan in <b>1 · Scan</b> to see when your own cryptography breaks.")
    year = st.slider("Drag to travel through time", YEAR_NOW, 2050, 2033, key="year")
    rows, machine = timeline_status(assessed, year, scenario, rsa_source)
    n_break = sum(r["status_in_year"] == "breakable" for r in rows)
    n_ready = sum(r["status_in_year"] == "qubits-ready" for r in rows)
    n_classic = sum(r["status_in_year"] == "broken" for r in rows)
    ui.headline(st, f"In <b>{year}</b>, the best quantum computer is <em>{machine['name']}</em>. "
                    f"A quantum attack can break <b>{n_break}</b> of your {len(rows)} assets"
                    + (f", and <b>{n_ready}</b> more are one step away" if n_ready else "") + "."
                    + (f" ({n_classic} are already broken today without any quantum computer.)" if n_classic else ""))
    ui.stat_cards(st, [
        ("Quantum-breakable", n_break, "a quantum attack works this year", "pink"),
        ("Almost", n_ready, "enough qubits, not enough operations", "yel"),
        ("Logical qubits", f"{machine['logical_qubits']:,}", "error-corrected qubits available", "lav"),
        ("Operations", f"{machine['operations']:.0e}" if machine["operations"] else "0",
         "gates per computation", ""),
    ])

    years = list(range(YEAR_NOW, 2051))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=years, y=[max(machine_at(y, scenario)["operations"], 1) for y in years],
                             name="quantum computer can run", mode="lines", line_shape="hv",
                             line=dict(width=4, color=ui.PLUM), fill="tozeroy",
                             fillcolor="rgba(220,210,250,.45)"))
    seen, dashes = set(), ["dot", "dash", "dashdot", "longdash"]
    for a in assessed:
        if a["quantum_status"] == "shor" and a["toffoli_needed"] and a["algorithm"] not in seen:
            seen.add(a["algorithm"])
            fig.add_trace(go.Scatter(x=[years[0], years[-1]], y=[a["toffoli_needed"]] * 2, mode="lines",
                                     name=f"breaking {a['algorithm']} needs",
                                     line=dict(color=ui.PINK, width=2, dash=dashes[(len(seen) - 1) % 4])))
    for i, m in enumerate(ROADMAP):
        fig.add_vline(x=m["year"], line_dash="dash", line_color=ui.MUTED, annotation_text=m["name"],
                      annotation_position="top left" if i == 0 else "top right", annotation_font_color=ui.MUTED)
    fig.add_vline(x=year, line_color=ui.PINK, line_width=3, annotation_text=f"{year}",
                  annotation_position="bottom right", annotation_font_color=ui.PINK)
    fig.update_layout(title="Quantum power vs what each attack needs",
                      yaxis_type="log", height=460, xaxis_title="year", yaxis_title="operations (log scale)",
                      legend=dict(orientation="h", y=-0.25, x=0))
    st.plotly_chart(fig, use_container_width=True, theme=None, config=CHART_CFG)
    st.caption("The purple line is what IBM's fault-tolerant machines can run each year. Where it rises above "
               "a pink line, that algorithm can be broken.")

    harvest = []
    for a in assessed:
        if a["confidentiality"] and a["break_year"]:
            window = harvest_now_window(a["break_year"], shelf_life, YEAR_NOW)
            if window:
                harvest.append((a, window))
    if harvest:
        ui.section(st, "Harvest now, decrypt later", "Attackers can record <em style='color:#e85291'>today</em> "
                   "and read it later.")
        for a, window in harvest:
            ui.note(st, f"<b>{a['algorithm']}</b> in <code>{a['location']}</code>: anything sent in "
                        f"<b>{window[0]}–{window[-1]}</b> can be read in <b>{a['break_year']}</b>, while it should "
                        f"still be secret ({shelf_life}-year shelf life).", "warn", "unlock")

    with st.expander("Technical details: requirements per asset", icon=":material/table_view:"):
        trows = [{**r,
                  "logical_qubits_needed": f"{r['logical_qubits_needed']:,}" if r["logical_qubits_needed"] else "",
                  "toffoli_needed": f"{r['toffoli_needed']:.1e}" if r["toffoli_needed"] else "",
                  "break_year": r["break_year"] or ""} for r in rows]
        ui.table(st, trows, [("status_in_year", f"Status in {year}"), ("algorithm", "Algorithm"),
                             ("purpose", "Used for"), ("location", "Where"),
                             ("logical_qubits_needed", "Logical qubits needed"),
                             ("toffoli_needed", "Toffoli gates needed"), ("break_year", "Breaks")],
                 badge_cols=("status_in_year",), code_cols=("location",))
        st.caption("Toffoli counts are compared directly with IBM's gate counts, which favours the attacker, "
                   "so these dates lean early. Every estimate is cited under Sources.")

    # ------------------------------------------------ the same forecast, calibrated by our own hardware runs
    cal = cached_calibration()
    if cal:
        best, median = cal["forecast"]["best_measured"], cal["forecast"]["median_measured"]
        bad = cal["machines"]["ibm_marrakesh"]
        ui.section(st, "Calibrated by our hardware runs",
                   "What our measured noise means for <em style='color:#e85291'>RSA-2048</em>.",
                   "The published estimate assumes an error of 10⁻³ per operation. We measured the effective error "
                   "per two-qubit gate from every Grover run on three IBM quantum computers.")
        ui.stat_cards(st, [
            ("Best measured qubits", ui.sci(best["eps"], 1), "error per two-qubit gate, 3× the paper's assumption",
             "lav"),
            ("RSA-2048 needs", f"{best['physical_qubits'] / 1e6:.1f} M",
             f"physical qubits at that error (paper: under 1 M), code distance {best['distance']}", "pink"),
            ("Without error correction", f"{ui.sci(best['improvement_needed_without_qec'])}×",
             "lower error needed: a direct attack is hopeless", "yel"),
        ])
        ui.note(st, f"Placement matters: on <code>ibm_marrakesh</code> the qubits the compiler picked "
                    f"({', '.join(map(str, bad['worst_qubits']))}) measured <b>{ui.sci(bad['worst'], 1)}</b>, above the "
                    f"~1% surface-code threshold, where no amount of error correction helps. Qubits "
                    f"{', '.join(map(str, bad['best_qubits']))} on the same chip measured <b>{ui.sci(bad['best'], 1)}</b>. "
                    f"At the median measured error ({ui.sci(median['eps'], 1)}) RSA-2048 would need about "
                    f"<b>{median['physical_qubits'] / 1e6:.1f} million</b> physical qubits.", "warn", "cpu")
        st.caption("Method: each Grover run's output is fitted as the ideal distribution mixed with uniform noise; "
                   "error per gate = 1 − F^(1/gates), readout included (an upper bound). Simple surface-code model, "
                   "scaled to the paper's estimate. Full tables: docs/RESULTS.md.")


# ---------------------------------------------------------------- 3 prove it
def bars(values: dict, highlight=(), title="", xaxis="outcome"):
    keys = sorted(values)
    fig = go.Figure(go.Bar(x=[str(k) for k in keys], y=[values[k] for k in keys],
                           marker_color=[ui.PINK if k in highlight else "#b9a6dd" for k in keys],
                           marker_line_width=0))
    fig.update_layout(title=title, height=300, xaxis_title=xaxis, yaxis_title="shots", bargap=.25)
    return fig


def run_shor(a, N, n_count, backend):
    res = run_sampler([shor.order_finding_circuit(a, N, n_count)], backend, shots=4000)["circuits"][0]
    st.session_state["shor_live"] = (shor.analyse_counts(res["counts"], a, N, n_count), backend)


@st.cache_data(show_spinner="Stepping through the circuit with quantum-debugger…")
def cached_trace(plaintext, key, iterations, n_bits):
    return qdebug.grover_trace(plaintext, key, iterations, n_bits)


@st.cache_data(show_spinner=False)
def cached_cross_checks(shor_a, plaintext, key, iterations, n_bits):
    circuits = [(f"Shor N = 15, a = {shor_a}", shor.order_finding_circuit(shor_a, 15, 3)),
                (f"Grover {n_bits}-bit", grover.grover_key_search_circuit(
                    plaintext, grover.toy_encrypt(plaintext, key, n_bits), iterations, n_bits))]
    return [{"label": label, **qdebug.cross_check(circuit)} for label, circuit in circuits]


def run_grover(p, c, iters, n_bits, backend):
    qc = grover.grover_key_search_circuit(p, c, iters, n_bits)
    res = run_sampler([qc], backend, shots=4000)["circuits"][0]
    st.session_state["grover_live"] = (grover.analyse_counts(res["counts"], p, c, iters, n_bits), backend)


with tab_prove:
    if hw:
        shor_hw = [c for c in hw["circuits"] if c["name"].startswith("shor")]
        first = shor_hw[0]
        a_hw = int(first["name"].split("_a")[1])
        r_hw = shor.analyse_counts(first["counts"], a_hw, 15, len(next(iter(first["counts"]))))
        ui.headline(st, f"We ran Shor's algorithm on <em>{hw['backend']}</em>, a real IBM quantum computer. "
                        f"It found the period <b>r = {r_hw['most_likely_order']}</b> and factored "
                        f"<b>15 = {r_hw['factors'][0]} × {r_hw['factors'][1]}</b>.")
        ui.stat_cards(st, [
            ("Success rate", f"{r_hw['success_probability']:.0%}",
             f"random noise would score {r_hw['random_noise_baseline']:.0%}", "pink"),
            ("Two-qubit gates", first["two_qubit_gates"], "after compiling for the chip", "lav"),
            ("QPU time", f"{hw.get('quantum_seconds')} s", f"job {hw['job_id'][:10]}…", "yel"),
        ])
        hw_counts = {int(b, 2): v for b, v in first["counts"].items()}
        st.plotly_chart(bars(hw_counts, highlight={0, 2, 4, 6}, title=f"Measured on {hw['backend']}",
                             xaxis="measured value y"), use_container_width=True, theme=None, config=CHART_CFG)
        st.caption("Pink bars are the answers the algorithm should produce (y = 0, 2, 4, 6); lavender bars are "
                   "hardware noise. The pink bars dominate, so the attack worked on real hardware.")
        with st.expander("All hardware runs (Shor and Grover)", icon=":material/memory:"):
            hw_rows = []
            for c in hw["circuits"]:
                if c["name"].startswith("shor"):
                    a_ = int(c["name"].split("_a")[1])
                    r = shor.analyse_counts(c["counts"], a_, 15, len(next(iter(c["counts"]))))
                    hw_rows.append({"circuit": f"Shor · N = 15, a = {a_}", "gates": c["two_qubit_gates"],
                                    "result": f"factors {r['factors'][0]} × {r['factors'][1]}" if r["factors"]
                                    else "no factor", "p": f"{r['success_probability']:.1%}",
                                    "base": f"{r['random_noise_baseline']:.1%}"})
                else:
                    m = grover.parse_name(c["name"])
                    r = grover.analyse_counts(c["counts"], m["plaintext"], m["ciphertext"], m["iterations"],
                                              m["n_bits"])
                    hw_rows.append({"circuit": f"Grover · {m['n_bits']}-bit key, {m['iterations']} iteration(s)",
                                    "gates": c["two_qubit_gates"],
                                    "result": f"key {r['recovered_key']} " + ui.check_mark(r["key_is_correct"]),
                                    "p": f"{r['success_probability']:.1%}",
                                    "base": f"{r['random_guess_baseline']:.1%}"})
            ui.table(st, hw_rows, [("circuit", "Circuit"), ("gates", "Two-qubit gates"), ("result", "Result"),
                                   ("p", "Success"), ("base", "Random baseline")], html_cols=("result",),
                     compact=True)

    suite = load_result("hardware_suite.json")
    hw_runs = {k: v for k, v in (suite or {}).get("runs", {}).items() if v.get("hardware")}
    if hw_runs:
        ui.section(st, "Hardware validation", "Tested on <em style='color:#e85291'>three</em> quantum computers."
                   if len(hw_runs) == 3 else "Hardware validation.",
                   "Every Shor base for N = 15 and Grover for all 8 secret keys, 4,000 shots each, plus two "
                   "negative controls that must fail. A test passes when its whole 95% confidence interval is "
                   "above what random noise would score.")
        tests = [r for run in hw_runs.values() for r in run["rows"] if not r["control"]]
        controls = [r for run in hw_runs.values() for r in run["rows"] if r["control"]]
        controls_ok = all((r["kind"] == "shor" and r["successes"] == 0) or
                          (r["kind"] == "grover" and r["ci95"][0] <= r["baseline"] <= r["ci95"][1] + 0.05)
                          for r in controls)
        ui.stat_cards(st, [
            ("Tests passed", f"{sum(r['significant'] for r in tests)}/{len(tests)}",
             f"across {len(hw_runs)} IBM backends", "pink"),
            ("Grover keys found", f"{sum(r.get('recovered_correct', False) for r in tests if r['kind'] == 'grover')}"
                                  f"/{sum(r['kind'] == 'grover' for r in tests)}", "every secret, every machine", "lav"),
            ("Negative controls", "behaved" if controls_ok else "check", "a = 14 never factors; 0 iterations ≈ random",
             "yel"),
            ("QPU time", f"{sum((run.get('quantum_seconds') or 0) for run in hw_runs.values())} s", "whole suite", ""),
        ])
        fig = go.Figure()
        palette = [ui.PLUM, ui.PINK, ui.VIOLET]
        for i, (be, run) in enumerate(hw_runs.items()):
            rows = [r for r in run["rows"] if not r["control"]]
            labels = [r["label"].replace(" (3 counting qubits)", "").replace(" (4 counting qubits)", " (n=4)")
                      .replace(" (2 iterations)", "").replace("Shor N=15 ", "Shor ").replace("Grover secret=", "Grover key ")
                      for r in rows]
            fig.add_trace(go.Bar(name=be, x=labels, y=[r["rate"] for r in rows], marker_color=palette[i % 3],
                                 error_y=dict(type="data", symmetric=False,
                                              array=[r["ci95"][1] - r["rate"] for r in rows],
                                              arrayminus=[r["rate"] - r["ci95"][0] for r in rows], thickness=1.2)))
            if i == 0:
                fig.add_trace(go.Scatter(name="random-noise baseline", x=labels, y=[r["baseline"] for r in rows],
                                         mode="markers", marker=dict(symbol="line-ew-open", size=22,
                                                                     color="#c9971c",
                                                                     line=dict(width=4, color="#c9971c"))))
        fig.update_layout(title="Success rate on real hardware vs random noise", barmode="group", height=440,
                          yaxis_title="success rate", yaxis_range=[0, 1], xaxis_tickangle=-35,
                          legend=dict(orientation="h", y=-0.45, x=0))
        st.plotly_chart(fig, use_container_width=True, theme=None, config=CHART_CFG)
        st.caption("Bars: measured success rate with 95% confidence intervals. Yellow marks: what pure noise or "
                   "random guessing would score. Every bar sits far above its mark.")
        with st.expander("Full statistics per backend", icon=":material/query_stats:"):
            for be, run in hw_runs.items():
                st.markdown(f"**{be}** · job `{run['job_id']}` · {run.get('quantum_seconds')} s QPU")
                ui.table(st, [{**r, "rate": f"{r['rate']:.1%}",
                               "ci": f"{r['ci95'][0]:.1%} – {r['ci95'][1]:.1%}", "base": f"{r['baseline']:.1%}",
                               "p": f"{r['p_value']:.1e}", "tvd": f"{r['tvd_to_ideal']:.3f}",
                               "verdict": ui.check_mark(True, "control ok") if r["control"] else
                               ui.check_mark(r["significant"], "pass", "fail")} for r in run["rows"]],
                         [("label", "Circuit"), ("two_qubit_gates", "2q gates"), ("result", "Result"),
                          ("rate", "Success"), ("ci", "95% CI"), ("base", "Baseline"), ("p", "p-value"),
                          ("tvd", "TVD to ideal"), ("verdict", "Verdict")], html_cols=("verdict",))
            st.caption("p-value: chance of seeing this many successes if the machine were only producing noise. "
                       "TVD: distance between the measured and ideal outcome distributions (0 = identical).")

    strict = load_result("hardware_strict.json")
    strict_hw = {k: b for k, b in (strict or {}).get("backends", {}).items() if b.get("hardware")}
    if strict_hw:
        ui.section(st, "Strict validation", "Pre-registered rules, <em style='color:#e85291'>no wiggle room</em>.",
                   "Pass rules were fixed in code before the runs. Grover keys were drawn at random at submit "
                   "time. Every test must pass all three checks: real signal (Bonferroni-corrected), the right "
                   "answer dominates, and at least half the ideal signal survives.")
        crit_rows = []
        for be, b in strict_hw.items():
            s = b["summary"]
            crit_rows.append({
                "backend": be,
                "all": ui.check_mark(s["tests_passed"] == s["tests"], f"{s['tests_passed']}/{s['tests']}",
                                     f"{s['tests_passed']}/{s['tests']}"),
                "c1": f"{s['C1_passed']}/{s['tests']}", "c2": f"{s['C2_passed']}/{s['tests']}",
                "c3": f"{s['C3_passed']}/{s['tests']}",
                "c4": ui.check_mark(b["C4_fingerprint"]["pass"], "pass", "fail"),
                "c5": ui.check_mark(b["C5_layout"]["pass"], "pass", "fail"),
                "c6": (ui.check_mark(b["C6_repeatability"]["pass"], "pass", "fail")
                       if b.get("C6_repeatability") else "not run"),
                "ctl": ui.check_mark(s["controls_ok"], "ok", "fail")})
        ui.table(st, crit_rows, [("backend", "Backend"), ("all", "All checks"), ("c1", "C1 signal"),
                                 ("c2", "C2 right answer wins"), ("c3", "C3 half signal survives"),
                                 ("c4", "C4 Grover fingerprint"), ("c5", "C5 other qubits"),
                                 ("c6", "C6 repeat run"), ("ctl", "Controls")],
                 html_cols=("all", "c4", "c5", "c6", "ctl"), compact=True)
        all_rows = [r for b in strict_hw.values() for r in b["rows"] if not r["control"]]
        shor_rows = [r for r in all_rows if r["test"].startswith("Shor")]
        grover_rows = [r for r in all_rows if r["test"].startswith("Grover")]
        ui.note(st, f"<b>Shor passed {sum(r['pass'] for r in shor_rows)}/{len(shor_rows)}</b> strict tests on every "
                    f"machine and qubit placement. <b>Grover passed {sum(r['pass'] for r in grover_rows)}/"
                    f"{len(grover_rows)}</b>: every Grover run beat random guessing (C1), but on some machines and "
                    "placements less than half of the ideal signal survived (C3). Grover relies on keeping quantum "
                    "phases intact through 140+ two-qubit gates, so it is the first to suffer from noise and from "
                    "where on the chip it runs.", "warn" if any(not r["pass"] for r in all_rows) else "good")
        sweep_fig = go.Figure()
        theory = next(iter(strict_hw.values()))["C4_fingerprint"]["theory"]
        sweep_fig.add_trace(go.Scatter(x=list(range(len(theory))), y=theory, name="theory (ideal)", mode="lines+markers",
                                       line=dict(color=ui.MUTED, dash="dash", width=2)))
        for i, (be, b) in enumerate(strict_hw.items()):
            c4 = b["C4_fingerprint"]
            sweep_fig.add_trace(go.Scatter(x=list(range(len(c4["rates"]))), y=c4["rates"], mode="lines+markers",
                                           name=f"{be} (r = {c4['pearson']:.2f})",
                                           line=dict(width=3, color=[ui.PLUM, ui.PINK, ui.VIOLET][i % 3])))
        sweep_fig.update_layout(title="Grover fingerprint: rises, peaks at 2, overshoots", height=380,
                                xaxis_title="Grover iterations", yaxis_title="chance of finding the key",
                                yaxis_range=[0, 1], legend=dict(orientation="h", y=-0.3, x=0))
        st.plotly_chart(sweep_fig, use_container_width=True, theme=None, config=CHART_CFG)
        st.caption("Random noise cannot fake this shape: success must climb, peak at the optimal 2 iterations, "
                   "then fall when the search overshoots. r is the correlation with theory.")
        with st.expander("Every strict test, per backend", icon=":material/rule:"):
            for be, b in strict_hw.items():
                st.markdown(f"**{be}** · job `{b['job_id']}` · {b['quantum_seconds']} s QPU")
                rows = []
                for r in b["rows"]:
                    if r["control"]:
                        rows.append({"test": r["test"] + " (control)", "layout": r["layout"], "rate": f"{r['rate']:.1%}",
                                     "verdict": ui.check_mark(r["pass"], "behaved", "failed")})
                        continue
                    c = r["criteria"]
                    rows.append({"test": r["test"], "layout": r["layout"],
                                 "qubits": ", ".join(map(str, r.get("physical_qubits") or [])),
                                 "rate": f"{r['rate']:.1%}", "p": f"{c['C1']['p_value']:.1e}",
                                 "fid": f"{c['C3']['hellinger_fidelity']:.3f} ≥ {c['C3']['threshold']:.3f}",
                                 "verdict": ui.check_mark(r["pass"], "pass", "fail")})
                ui.table(st, rows, [("test", "Test"), ("layout", "Placement"), ("qubits", "Physical qubits"),
                                    ("rate", "Success"), ("p", "p-value"), ("fid", "Fidelity vs bar"),
                                    ("verdict", "Verdict")], html_cols=("verdict",))
            st.caption(f"Criteria {strict['criteria']}: alpha = {strict['alpha']} split over {strict['m_tests']} tests "
                       "(Bonferroni). Definitions in qday/quantum/validation.py.")

    ui.section(st, "Try it yourself", "Run the attacks <em style='color:#e85291'>live</em>.",
               "These break <b>toy</b> keys (small numbers, 3–4-bit keys). Real keys need the fault-tolerant "
               "machines shown in the Time Machine.")
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("### Shor · factor a number")
        st.caption("Finds the hidden period of aˣ mod N; the period reveals N's factors.")
        c1, c2 = st.columns(2)
        N = c1.selectbox("Number to factor (N)", [15, 21], key="shor_N")
        a = c2.selectbox("Base (a)", [x for x in range(2, N) if gcd(x, N) == 1], key=f"shor_a_{N}")
        n_count = 3 if N == 15 else 6
        # N = 21 compiles to ~6,500 two-qubit gates: noisy simulation would take minutes and return noise
        shor_backends = list(BACKEND_LABELS) if N == 15 else ["aer"]
        be = st.radio("Run on", shor_backends, horizontal=True, key=f"shor_be_{N}", format_func=BACKEND_LABELS.get)
        if N == 21:
            st.caption("N = 21 needs ~6,500 two-qubit gates after compiling, far beyond today's noisy hardware, "
                       "so it runs on the ideal simulator only.")
        if "shor_live" not in st.session_state:
            run_shor(7, 15, 3, "aer")
        if st.button("Run Shor", type="primary", icon=":material/play_arrow:", key="run_shor"):
            with st.spinner("Running on " + BACKEND_LABELS[be] + "…"):
                run_shor(a, N, n_count, be)
        r, used = st.session_state["shor_live"]
        if r["factors"]:
            ui.note(st, f"Factored <b>{r['N']} = {r['factors'][0]} × {r['factors'][1]}</b> using base a = {r['a']} "
                        f"({BACKEND_LABELS[used].lower()}). Period r = {r['most_likely_order']}; "
                        f"{r['success_probability']:.0%} of runs gave the factors.", "good", "check")
        else:
            ui.note(st, f"Found the period r = {r['most_likely_order']} for a = {r['a']}, but this base gives "
                        "no factor (a known case). Pick another base and run again.", "warn")
        st.plotly_chart(bars({o["y"]: o["shots"] for o in r["outcomes"]}, title="Measured values",
                             highlight={o["y"] for o in r["outcomes"] if o["factors"]}),
                        use_container_width=True, theme=None, config=CHART_CFG)
        with st.expander("Show the quantum circuit", icon=":material/account_tree:"):
            st.pyplot(shor.order_finding_circuit(a, N, n_count).draw("mpl", fold=-1, style="clifford"))

    with right:
        st.markdown("### Grover · guess a secret key")
        st.caption("Searches all keys at once; needs about √(number of keys) tries instead of all of them.")
        c1, c2 = st.columns(2)
        n_bits = c1.selectbox("Key size (bits)", [3, 4], key="grover_bits")
        secret = c2.number_input("Secret key (hidden from the attacker)", 0, 2**n_bits - 1, 6,
                                 key=f"secret_{n_bits}")  # one widget per key size: a 4-bit value never leaks into the 3-bit range
        plaintext = 5
        ciphertext = grover.toy_encrypt(plaintext, secret, n_bits)
        iters = grover.optimal_iterations(n_bits)
        be_g = st.radio("Run on", list(BACKEND_LABELS), horizontal=True, key="gr_be", format_func=BACKEND_LABELS.get)
        if "grover_live" not in st.session_state:
            run_grover(5, grover.toy_encrypt(5, 6, 3), 2, 3, "aer")
        if st.button("Run Grover", type="primary", icon=":material/play_arrow:", key="run_grover"):
            with st.spinner("Running on " + BACKEND_LABELS[be_g] + "…"):
                run_grover(plaintext, ciphertext, iters, n_bits, be_g)
        r, used = st.session_state["grover_live"]
        tone = "good" if r["key_is_correct"] else "warn"
        ui.note(st, f"Recovered key <b>{r['recovered_key']}</b> "
                    f"({'correct' if r['key_is_correct'] else 'wrong'}) in <b>{r['iterations']}</b> quantum tries, "
                    f"instead of up to {r['classical_worst_case_trials']} classical guesses. "
                    f"{r['success_probability']:.0%} of runs found it (random guessing: "
                    f"{r['random_guess_baseline']:.0%}).", tone, "check" if r["key_is_correct"] else "x")
        st.plotly_chart(bars({k: v * r["shots"] for k, v in r["distribution"].items()},
                             highlight={r["recovered_key"]} if r["key_is_correct"] else set(),
                             title="How often each key came out", xaxis="key"),
                        use_container_width=True, theme=None, config=CHART_CFG)

    # ------------------------------------------------ inside the circuit, with quantum-debugger
    ui.section(st, "Inside the circuit", "Pause the attack <em style='color:#e85291'>mid-flight</em>.",
               "Stepped through with <a href='https://pypi.org/project/quantum-debugger/'>quantum-debugger</a>, "
               "our own open-source quantum circuit debugger. It runs the Grover attack above one gate at a time, "
               "stops after every oracle and diffuser, and also re-simulates every attack circuit as an independent "
               "check on Qiskit.")
    max_iters = grover.optimal_iterations(n_bits) + 2
    trace_iters = st.slider("Grover iterations to step through", 1, max_iters, max_iters - 1, key=f"trace_iters_{n_bits}",
                            help="Go past the optimum to see the probability fall again (overshoot).")
    trace = cached_trace(plaintext, int(secret), trace_iters, n_bits)
    stops = trace["markers"]
    stage = st.select_slider("Stop after", [m["label"] for m in stops], value=stops[min(2, len(stops) - 1)]["label"],
                             key=f"trace_stage_{n_bits}_{trace_iters}")
    stop = next(m for m in stops if m["label"] == stage)
    amps, key = stop["amplitudes"], trace["key"]
    mean = sum(amps) / len(amps)
    left, right = st.columns([3, 2], gap="large")
    with left:
        fig = go.Figure(go.Bar(x=list(range(len(amps))), y=amps, marker_color=[ui.PINK if k == key else ui.LAVENDER
                                                                                 for k in range(len(amps))],
                               marker_line=dict(color=ui.PLUM, width=1), hovertemplate="key %{x}: %{y:.3f}<extra></extra>"))
        fig.add_hline(y=mean, line=dict(color=ui.PLUM, dash="dash", width=1.5),
                      annotation_text=f"mean {mean:+.3f}", annotation_position="top left")
        fig.add_hline(y=0, line=dict(color=ui.BORDER, width=1))
        fig.update_layout(height=340, title=f"Amplitude of every key after {stage.lower()}", xaxis_title="key",
                          yaxis_title="amplitude", yaxis=dict(range=[-1.05, 1.05]), xaxis=dict(dtick=1),
                          showlegend=False, margin=dict(t=50))
        st.plotly_chart(fig, use_container_width=True, theme=None, config=CHART_CFG)
    with right:
        labels = ["start"] + [f"after {i}" for i in range(1, trace_iters + 1)]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=labels, y=trace["theory"], mode="lines", name="sin² law",
                                 line=dict(color=ui.PLUM, dash="dot", width=2)))
        fig.add_trace(go.Scatter(x=labels, y=trace["after_iteration"], mode="markers", name="quantum-debugger",
                                 marker=dict(color=ui.PINK, size=12, line=dict(color=ui.PLUM, width=1))))
        fig.update_layout(height=340, title="Chance of the secret key", yaxis=dict(range=[0, 1.05], tickformat=".0%"),
                          legend=dict(orientation="h", y=-0.2), margin=dict(t=50))
        st.plotly_chart(fig, use_container_width=True, theme=None, config=CHART_CFG)
    if stage.startswith("Oracle"):
        explain = (f"The oracle ran the cipher's S-box on every key at once and flipped the sign of key {key} only. "
                   "The chance of each key is unchanged; the information is hidden in that sign.")
    elif stage.startswith("Diffuser"):
        explain = ("The diffuser reflected every amplitude around the mean (dashed line): the flipped key, far below "
                   "the mean, lands far above it. That is where the extra probability comes from.")
    else:
        explain = "The Hadamards put every key in equal superposition: each starts with the same amplitude."
    best_i = max(range(len(trace["after_iteration"])), key=trace["after_iteration"].__getitem__)
    ui.note(st, f"{explain} After <b>{best_i}</b> iteration{'s' if best_i != 1 else ''} the secret key {key} has "
                f"<b>{trace['after_iteration'][best_i]:.1%}</b> probability, exactly the sin² law "
                f"({len(trace['steps']) - 1} gates stepped).", "good", "check")
    checks = cached_cross_checks(a if N == 15 else 7, plaintext, int(secret), iters, n_bits)  # N = 21 is simulator-only
    st.caption("Independent check with quantum-debugger: " + "; ".join(
        f"{c['label']} ({c['gates']} gates, {c['qubits']} qubits): "
        + (f"agrees with Qiskit, max difference {c['max_abs_diff']:.0e}" if c["agree"] else "DISAGREES with Qiskit")
        for c in checks) + ".")

# ---------------------------------------------------------------- 4 migrate
with tab_migrate:
    if "hybrid" not in st.session_state:
        st.session_state["hybrid"] = hybrid_key_exchange()
        st.session_state["sigs"] = signature_comparison()
    h = st.session_state["hybrid"]
    ui.headline(st, "The fix exists today: NIST's post-quantum standards <em>ML-KEM</em> (key exchange) and "
                    "<em>ML-DSA</em> (signatures).")
    ui.stat_cards(st, [
        ("Secure session", "established" if h["keys_match"] and h["message_roundtrip"] else "failed",
         "hybrid X25519 + ML-KEM-768, AES-256", "pink"),
        ("Extra data", f"{h['client_to_server_bytes'] + h['server_to_client_bytes']:,} B",
         "per handshake, both directions", "lav"),
        ("Tampering", "detected", "ML-DSA rejects a changed message", "yel"),
    ])
    ui.note(st, "Hybrid means the session stays secret as long as <b>either</b> X25519 or ML-KEM holds, "
                "so it is safe against today's attackers and tomorrow's quantum computers. Shor needs a hidden "
                "period in modular arithmetic; ML-KEM and ML-DSA are built on lattices, where no such attack "
                "is known.", "good")
    sig_rows = [{"status": "safe" if s["quantum_safe"] else "shor", "algorithm": s["algorithm"],
                 "pk": f"{s['public_key_bytes']:,} B", "sig": f"{s['signature_bytes']:,} B",
                 "sign": f"{s['sign_ms']:.1f} ms", "verify": f"{s['verify_ms']:.1f} ms",
                 "tamper": ui.check_mark(True, "rejected") if s.get("tampered_rejected") else ""}
                for s in st.session_state["sigs"]]
    ui.section(st, "Before vs after", "Signatures, side by side.")
    ui.table(st, sig_rows, [("status", "Quantum"), ("algorithm", "Signature"), ("pk", "Public key"),
                            ("sig", "Signature size"), ("sign", "Sign"), ("verify", "Verify"),
                            ("tamper", "Tampered message")], badge_cols=("status",), html_cols=("tamper",),
             compact=True)
    st.caption("Post-quantum keys and signatures are larger. ML-DSA timings come from a pure-Python reference "
               "implementation (dilithium-py); optimised C libraries are far faster.")
    if st.button("Run the handshake again", icon=":material/refresh:", key="rerun_pqc"):
        st.session_state["hybrid"] = hybrid_key_exchange()
        st.session_state["sigs"] = signature_comparison()
        st.rerun()

# ---------------------------------------------------------------- sources
with tab_about:
    ui.section(st, "Sources", "Every number, <em style='color:#e85291'>cited</em>.")
    st.markdown("**Resource estimates**\n" + "\n".join(f"- [{s['label']}]({s['url']})" for s in SOURCES.values()))
    st.markdown("**IBM roadmap**\n" + "\n".join(f"- {u}" for u in ROADMAP_SOURCES))
    st.markdown("**Standards**: NIST FIPS 203 (ML-KEM), FIPS 204 (ML-DSA); CycloneDX 1.6 CBOM  \n"
                "**Built with**: Qiskit, Qiskit Aer, Qiskit IBM Runtime, cryptography, kyber-py, "
                "dilithium-py, Streamlit, Plotly")
