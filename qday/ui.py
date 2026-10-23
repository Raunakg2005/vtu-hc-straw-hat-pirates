"""Presentation helpers: Fall Fest styling, hero, cards, icons, badge tables and a Plotly template."""

import html

import plotly.graph_objects as go
import plotly.io as pio

PLUM, PINK, LAVENDER, YELLOW, CREAM, BG = "#392045", "#e85291", "#dcd2fa", "#f4c84e", "#fff9f3", "#f4efff"
MUTED, BORDER, VIOLET, GREEN, BERRY = "#756879", "#d8cadc", "#7a5cb8", "#2f8f6b", "#b3245e"

# Icon paths in the style of the Lucide set (24x24 viewBox, stroke-based).
ICONS = {
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "shield-check": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/><path d="m9 12 2 2 4-4"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>'
             '<path d="M12 9v4"/><path d="M12 17h.01"/>',
    "unlock": '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',
    "cpu": '<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/>'
           '<path d="M15 2v2M15 20v2M2 15h2M2 9h2M20 15h2M20 9h2M9 2v2M9 20v2"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "arrow-left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
}

BADGE = {  # label -> (background, text)
    "critical": (BERRY, CREAM), "high": (PINK, CREAM), "medium": (YELLOW, PLUM),
    "safe": (GREEN, CREAM), "unknown": (MUTED, CREAM),
    "breakable": (BERRY, CREAM), "broken": (BERRY, CREAM),
    "qubits-ready": (PINK, CREAM), "vulnerable (size unknown)": (PINK, CREAM),
    "weakened": (YELLOW, PLUM),
    "shor": (BERRY, CREAM), "grover": (YELLOW, PLUM), "classical": (PLUM, CREAM),
}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300..900;1,9..40,300..900&family=Fraunces:ital,opsz,wght@0,9..144,400..800;1,9..144,400..800&display=swap');

html, body, [class*="st-"], .stMarkdown, button, input, textarea, select {{
  font-family: "DM Sans", sans-serif !important;
}}
/* keep Streamlit's icon font: icons are ligatures, so overriding the font shows the icon's name as text */
[data-testid="stIconMaterial"], [data-testid="stIconMaterial"] *, [data-testid="stExpanderIcon"],
[data-testid$="Icon"], span[translate="no"], .material-symbols-rounded {{
  font-family: "Material Symbols Rounded" !important;
  font-weight: normal !important; font-style: normal !important; letter-spacing: normal !important;
  text-transform: none !important;
}}
.stApp {{
  background-color: {BG};
  background-image:
    linear-gradient(rgba(122,92,184,.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(122,92,184,.07) 1px, transparent 1px);
  background-size: 44px 44px;
}}
.stApp, .main {{ overflow-x: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}
/* hide Streamlit's menu and deploy button only: the toolbar also holds the button that reopens the sidebar */
[data-testid="stMainMenu"], [data-testid="stAppDeployButton"], [data-testid="stToolbarActions"],
[data-testid="stStatusWidget"] {{ display: none !important; }}
[data-testid="stExpandSidebarButton"] {{ background: {CREAM}; border: 1px solid {BORDER}; border-radius: 999px;
  padding: .3rem .85rem .3rem .55rem; box-shadow: 0 8px 22px -12px rgba(57,32,69,.45); color: {PLUM};
  display: inline-flex; align-items: center; gap: .35rem; transition: background-color .2s, color .2s; }}
[data-testid="stExpandSidebarButton"]::after {{ content: "Settings"; font-family: "DM Sans", sans-serif;
  font-weight: 800; font-size: .85rem; }}
[data-testid="stExpandSidebarButton"]:hover {{ background: {PLUM}; color: {CREAM}; }}
.block-container {{ padding-top: 2rem; max-width: 1280px; }}
h1, h2, h3, .ff-serif {{ font-family: "Fraunces", serif !important; color: {PLUM}; letter-spacing: -0.02em; }}

/* sidebar: forecast settings */
[data-testid="stSidebar"] {{ border-right: 1px solid {BORDER}; box-shadow: 10px 0 40px -30px rgba(57,32,69,.45); }}
[data-testid="stSidebarUserContent"] {{ padding-top: .25rem; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ font-size: 1.35rem; margin: 0; }}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ font-weight: 700; color: {PLUM}; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{ color: {MUTED}; }}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"][class*="border"],
[data-testid="stSidebar"] [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {{ background: #ffffff;
  box-shadow: 0 6px 20px -16px rgba(57,32,69,.5); }}
.ff-side-home {{ display: inline-flex; align-items: center; gap: .4rem; font-weight: 700; font-size: .85rem;
  color: {MUTED} !important; text-decoration: none !important; margin-bottom: .9rem; }}
.ff-side-home:hover {{ color: {PINK} !important; }}
.ff-side-group {{ display: flex; align-items: center; gap: .55rem; font-weight: 800; color: {PLUM}; font-size: .95rem;
  margin-bottom: .1rem; }}
.ff-side-group span {{ width: 28px; height: 28px; border-radius: 9px; display: grid; place-items: center;
  background: {LAVENDER}; color: {PLUM}; }}
.ff-icon {{ vertical-align: -3px; flex: 0 0 auto; }}

/* eyebrow label with dot */
.ff-eyebrow {{ color: {PINK}; font-weight: 800; font-size: .72rem; letter-spacing: .22em;
  text-transform: uppercase; display: flex; align-items: center; gap: .55rem; margin-bottom: .4rem; }}
.ff-eyebrow::before {{ content: ""; width: 7px; height: 7px; border-radius: 50%; background: {PINK}; flex: 0 0 auto; }}

/* hero */
.ff-hero {{ padding: .4rem 0 1.4rem 0; }}
.ff-hero h1 {{ font-size: clamp(2.1rem, 5vw, 4rem); line-height: 1.02; font-weight: 600; margin: 0 0 .6rem 0; }}
.ff-hero h1 em {{ color: {PINK}; font-style: italic; }}
.ff-hero p {{ color: {MUTED}; font-size: 1.08rem; max-width: 760px; margin: 0; }}

/* stat cards (countdown style) */
.ff-stats {{ display: grid; grid-template-columns: repeat(var(--n, 4), minmax(0, 1fr)); gap: .9rem; margin: .6rem 0 1.2rem 0; }}
.ff-card {{ background: {CREAM}; border: 1px solid {BORDER}; border-radius: 1.15rem; padding: 1rem 1.15rem;
  box-shadow: 0 6px 24px -14px rgba(57,32,69,.35); min-width: 0; }}
.ff-card .ff-k {{ color: {PINK}; font-weight: 800; font-size: .66rem; letter-spacing: .18em; text-transform: uppercase; }}
.ff-card .ff-v {{ font-family: "Fraunces", serif; font-size: 2rem; font-weight: 600; color: {PLUM}; line-height: 1.1;
  margin-top: .25rem; overflow-wrap: anywhere; }}
.ff-card .ff-s {{ color: {MUTED}; font-size: .82rem; margin-top: .2rem; }}
.ff-card.pink {{ background: #f7a8c8; border-color: #f095ba; }}
.ff-card.pink .ff-k, .ff-card.yel .ff-k {{ color: {BERRY}; }}
.ff-card.pink .ff-s, .ff-card.yel .ff-s, .ff-card.lav .ff-s {{ color: #5b4566; }}
.ff-card.lav  {{ background: {LAVENDER}; border-color: #c9bbf0; }}
.ff-card.yel  {{ background: #f8dc8b; border-color: #efcd6a; }}

/* callouts */
.ff-note {{ border-radius: 1.15rem; padding: .95rem 1.15rem; margin: .5rem 0 1rem 0; border: 1px solid {BORDER};
  background: {CREAM}; display: flex; gap: .8rem; align-items: flex-start; }}
.ff-note-icon {{ flex: 0 0 auto; margin-top: .05rem; }}
.ff-note.good {{ background: #e3f4ec; border-color: #b8e0cc; }}
.ff-note.warn {{ background: #fde6ef; border-color: #f5b9d1; }}
.ff-note b {{ color: {PLUM}; }}
.ff-note code {{ background: rgba(255,255,255,.7); color: {VIOLET}; padding: .05rem .35rem; border-radius: .35rem; }}

/* badge tables */
.ff-scroll {{ overflow-x: auto; border-radius: 1.15rem; margin-bottom: 1rem; -webkit-overflow-scrolling: touch; }}
.ff-table {{ width: 100%; min-width: 980px; border-collapse: separate; border-spacing: 0; background: {CREAM};
  border: 1px solid {BORDER}; border-radius: 1.15rem; overflow: hidden; font-size: .88rem; margin: 0; }}
.ff-table th, .ff-table td {{ border-left: none !important; border-right: none !important; border-bottom: none !important; }}
.ff-table th {{ border-top: none !important; background: {LAVENDER}; color: {PLUM}; text-align: left; font-weight: 800;
  font-size: .7rem; letter-spacing: .12em; text-transform: uppercase; padding: .7rem .8rem; }}
.ff-table td {{ padding: .62rem .8rem; border-top: 1px solid #efe6ef; color: {PLUM}; vertical-align: top; }}
.ff-table td:last-child {{ min-width: 240px; color: {MUTED}; font-size: .82rem; }}
.ff-table.compact {{ min-width: 640px; }}
.ff-table tr:hover td {{ background: #fbf3fa; }}
.ff-table code {{ background: {BG}; color: {VIOLET}; padding: .1rem .4rem; border-radius: .4rem; font-size: .8rem; }}
.ff-badge {{ display: inline-block; padding: .18rem .62rem; border-radius: 999px; font-weight: 800;
  font-size: .68rem; letter-spacing: .06em; text-transform: uppercase; white-space: nowrap; }}
.ff-muted {{ color: {MUTED}; font-size: .8rem; }}
.ff-ok {{ color: {GREEN}; font-weight: 700; white-space: nowrap; }}
.ff-bad {{ color: {BERRY}; font-weight: 700; white-space: nowrap; }}

/* tabs as pills; ARIA roles, not BaseWeb attributes, so this holds across Streamlit versions (1.66 moved to React Aria) */
.stTabs [role="tablist"] {{ gap: .4rem !important; background: {CREAM} !important; padding: .35rem !important;
  border-radius: 999px !important; border: 1px solid {BORDER} !important; width: fit-content; max-width: 100%;
  overflow-x: auto; scrollbar-width: none; box-shadow: none !important; }}
.stTabs [role="tab"] {{ border-radius: 999px !important; padding: .45rem 1.05rem !important; height: auto !important;
  font-weight: 700; color: {PLUM} !important; white-space: nowrap; border: none !important; box-shadow: none !important; }}
.stTabs [role="tab"]:hover {{ background: {BG}; }}
.stTabs [role="tab"][aria-selected="true"] {{ background: {PLUM} !important; color: {CREAM} !important; }}
.stTabs [role="tab"] p {{ color: inherit !important; font-weight: 700; }}
.stTabs [role="tab"]::after, .stTabs [role="tab"]::before {{ display: none !important; }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none; }}

/* buttons */
.stButton > button, .stDownloadButton > button {{ font-weight: 800; padding: .55rem 1.3rem; }}
.stButton > button[kind="primary"] {{ background: {PLUM}; border-color: {PLUM}; color: {CREAM}; }}
.stButton > button[kind="primary"]:hover {{ background: {PINK}; border-color: {PINK}; }}

[data-testid="stExpander"] {{ background: {CREAM}; border-radius: 1.15rem; }}

/* guided steps strip */
.ff-steps {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .8rem; margin: .2rem 0 1.4rem 0; }}
.ff-step {{ background: {CREAM}; border: 1px solid {BORDER}; border-radius: 1.15rem; padding: .85rem 1rem;
  display: flex; gap: .75rem; align-items: flex-start; }}
.ff-step-n {{ flex: 0 0 auto; width: 30px; height: 30px; border-radius: 50%; background: {PLUM}; color: {CREAM};
  font-family: "Fraunces", serif; font-weight: 700; display: grid; place-items: center; font-size: .95rem; }}
.ff-step-t {{ font-weight: 800; color: {PLUM}; font-size: .95rem; }}
.ff-step-d {{ color: {MUTED}; font-size: .8rem; line-height: 1.35; margin-top: .1rem; }}

/* grouped findings */
.ff-groups {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .9rem; margin: .4rem 0 1rem 0; align-items: start; }}
.ff-group {{ background: {CREAM}; border: 1px solid {BORDER}; border-radius: 1.15rem; padding: 1rem; min-width: 0; }}
.ff-group-h {{ display: flex; align-items: center; gap: .55rem; margin-bottom: .2rem; }}
.ff-group-h b {{ font-family: "Fraunces", serif; font-size: 1.2rem; color: {PLUM}; }}
.ff-group-c {{ margin-left: auto; font-family: "Fraunces", serif; font-size: 1.6rem; font-weight: 700; }}
.ff-group-sub {{ color: {MUTED}; font-size: .8rem; margin-bottom: .6rem; }}
.ff-find {{ background: #fff; border: 1px solid #efe6ef; border-radius: .9rem; padding: .7rem .8rem; margin-top: .55rem; }}
.ff-find-t {{ display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; font-weight: 800; color: {PLUM}; }}
.ff-find-w {{ color: {MUTED}; font-size: .78rem; margin-top: .2rem; overflow-wrap: anywhere; }}
.ff-find-p {{ font-size: .86rem; color: {PLUM}; margin-top: .35rem; }}
.ff-find-fix {{ font-size: .8rem; margin-top: .3rem; color: {GREEN}; font-weight: 700; }}
.ff-headline {{ font-family: "Fraunces", serif; font-size: 1.45rem; color: {PLUM}; line-height: 1.3; margin: .3rem 0 .9rem 0; }}
.ff-headline em {{ color: {PINK}; font-style: italic; }}

/* responsive */
@media (max-width: 1000px) {{
  .ff-stats.n4, .ff-steps {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .ff-groups {{ grid-template-columns: 1fr; }}
}}
@media (max-width: 900px) {{
  .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
  .ff-card .ff-v {{ font-size: 1.6rem; }}
}}
@media (max-width: 640px) {{
  .block-container {{ padding-top: 1rem; }}
  .ff-hero h1 {{ font-size: 2.1rem; }}
  .ff-hero p {{ font-size: .95rem; }}
  .ff-stats {{ gap: .6rem; }}
  .ff-stats.n3 {{ grid-template-columns: 1fr; }}
  .ff-steps {{ display: none; }}
  .ff-headline {{ font-size: 1.2rem; }}
  .ff-card {{ padding: .75rem .85rem; }}
  .ff-card .ff-v {{ font-size: 1.3rem; }}
  .ff-card .ff-k {{ font-size: .58rem; letter-spacing: .1em; }}
  .ff-card .ff-s {{ font-size: .74rem; }}
  .ff-section h2 {{ font-size: 1.55rem !important; }}
  .stTabs [role="tab"] {{ padding: .4rem .75rem !important; font-size: .85rem; }}
  .ff-note {{ padding: .8rem .9rem; font-size: .9rem; gap: .6rem; }}
  .ff-eyebrow {{ letter-spacing: .14em; font-size: .64rem; }}
}}
</style>
"""


def icon(name: str, color: str = None, size: int = 18) -> str:
    stroke = color or "currentColor"
    return (f'<svg class="ff-icon" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{stroke}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{ICONS[name]}</svg>')


def check_mark(ok: bool, yes: str = "correct", no: str = "wrong") -> str:
    """Icon + word, for HTML table cells."""
    if ok:
        return f'<span class="ff-ok">{icon("check", GREEN, 15)} {yes}</span>'
    return f'<span class="ff-bad">{icon("x", BERRY, 15)} {no}</span>'


def inject_css(st):
    st.markdown(CSS, unsafe_allow_html=True)


# Plain-language meaning of each quantum status, for non-specialists.
PLAIN = {
    "shor": "A large quantum computer running Shor's algorithm can break this.",
    "grover": "Quantum search (Grover) halves its strength. The 256-bit version is fine.",
    "classical": "Already broken today, even without a quantum computer.",
    "safe": "No known quantum attack.",
    "unknown": "Not in our catalog; check it manually.",
}


def steps(st, items):
    """Numbered how-it-works strip. items: list of (title, description)."""
    cells = "".join(f'<div class="ff-step"><div class="ff-step-n">{i}</div><div>'
                    f'<div class="ff-step-t">{html.escape(t)}</div><div class="ff-step-d">{html.escape(d)}</div>'
                    f'</div></div>' for i, (t, d) in enumerate(items, 1))
    st.markdown(f'<div class="ff-steps">{cells}</div>', unsafe_allow_html=True)


def headline(st, text_html):
    st.markdown(f'<div class="ff-headline">{text_html}</div>', unsafe_allow_html=True)


def finding_groups(st, groups):
    """groups: list of (title, subtitle, icon_name, color, findings). Each finding is an assessed asset."""
    cols = []
    for title, sub, icon_name, color, findings in groups:
        merged = {}  # one card per algorithm, listing every place it is used
        for f in findings:
            m = merged.setdefault((f["algorithm"], f["risk"]), {**f, "places": []})
            m["places"].append(f"{f['purpose']} · {f['location']}")
        items = []
        for f in merged.values():
            year = f"Breaks ≈ {f['break_year']} · " if f.get("break_year") else ""
            n = len(f["places"])
            where = "<br>".join(html.escape(p) for p in f["places"][:4])
            if n > 4:
                where += f"<br>+ {n - 4} more"
            fix = (f'<div class="ff-find-fix">{icon("check", GREEN, 14)} Fix: {html.escape(f["replacement"])}</div>'
                   if f.get("replacement") else "")
            items.append(
                f'<div class="ff-find"><div class="ff-find-t">{badge(f["risk"])} {html.escape(f["algorithm"])}'
                f'<span class="ff-muted" style="font-weight:600">{year}used in {n} place{"s" if n > 1 else ""}'
                f'</span></div><div class="ff-find-w">{where}</div>'
                f'<div class="ff-find-p">{html.escape(PLAIN.get(f["quantum_status"], ""))}</div>{fix}</div>')
        empty = '<div class="ff-muted" style="margin-top:.5rem">Nothing here.</div>'
        cols.append(f'<div class="ff-group"><div class="ff-group-h">{icon(icon_name, color, 22)}'
                    f'<b>{html.escape(title)}</b><span class="ff-group-c" style="color:{color}">{len(findings)}</span>'
                    f'</div><div class="ff-group-sub">{html.escape(sub)}</div>{"".join(items) or empty}</div>')
    st.markdown(f'<div class="ff-groups">{"".join(cols)}</div>', unsafe_allow_html=True)


def eyebrow(st, text):
    st.markdown(f'<div class="ff-eyebrow">{html.escape(text)}</div>', unsafe_allow_html=True)


def side_home(st, href="/"):
    """Link from the dashboard back to the landing page (served at / by serve.py)."""
    st.markdown(f'<a class="ff-side-home" href="{html.escape(href)}" target="_self">{icon("arrow-left", size=16)}'
                "Home</a>", unsafe_allow_html=True)


def side_group(st, icon_name, title):
    st.markdown(f'<div class="ff-side-group"><span>{icon(icon_name, size=16)}</span>{html.escape(title)}</div>',
                unsafe_allow_html=True)


def section(st, eyebrow_text, title_html, subtitle=None):
    sub = f'<p class="ff-muted" style="font-size:.98rem;margin:.2rem 0 .8rem 0">{subtitle}</p>' if subtitle else ""
    st.markdown(f'<div class="ff-section"><div class="ff-eyebrow">{html.escape(eyebrow_text)}</div>'
                f'<h2 style="margin:0;font-size:2rem">{title_html}</h2>{sub}</div>', unsafe_allow_html=True)


def hero(st, eyebrow_text, title_html, subtitle):
    st.markdown(f'<div class="ff-hero"><div class="ff-eyebrow">{html.escape(eyebrow_text)}</div>'
                f'<h1>{title_html}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def sci(value: float, decimals: int = 0) -> str:
    """2.4e8 -> '2×10⁸'; sci(3.06e-3, 1) -> '3.1×10⁻³' (superscript exponent)."""
    mantissa, exponent = f"{value:.{decimals}e}".split("e")
    return f"{mantissa}×10{str(int(exponent)).translate(str.maketrans('-0123456789', '⁻⁰¹²³⁴⁵⁶⁷⁸⁹'))}"


def stat_cards(st, cards):
    """cards: list of (label, value, sub_html, variant) with variant in '', 'pink', 'lav', 'yel'."""
    items = "".join(
        f'<div class="ff-card {v}"><div class="ff-k">{html.escape(k)}</div>'
        f'<div class="ff-v">{html.escape(str(val))}</div><div class="ff-s">{s}</div></div>'
        for k, val, s, v in cards)
    n = len(cards)
    st.markdown(f'<div class="ff-stats n{n}" style="--n:{n}">{items}</div>', unsafe_allow_html=True)


NOTE_ICONS = {"good": ("shield-check", GREEN), "warn": ("alert", BERRY), "": ("info", VIOLET)}


def note(st, body_html, kind="", icon_name=None):
    default_icon, color = NOTE_ICONS.get(kind, NOTE_ICONS[""])
    st.markdown(f'<div class="ff-note {kind}"><span class="ff-note-icon">'
                f'{icon(icon_name or default_icon, color, 22)}</span><div>{body_html}</div></div>',
                unsafe_allow_html=True)


def badge(label) -> str:
    bg, fg = BADGE.get(str(label), (MUTED, CREAM))
    return f'<span class="ff-badge" style="background:{bg};color:{fg}">{html.escape(str(label))}</span>'


def table(st, rows, columns, badge_cols=(), code_cols=(), html_cols=(), compact=False):
    """Render rows (list of dicts) as a themed HTML table. columns: list of (key, header).

    html_cols hold trusted, pre-built HTML (icons) and are inserted unescaped.
    """
    head = "".join(f"<th>{html.escape(h)}</th>" for _, h in columns)
    body = []
    for r in rows:
        cells = []
        for key, _ in columns:
            v = r.get(key)
            if v is None or v == "":
                cells.append('<td class="ff-muted">—</td>')
            elif key in badge_cols:
                cells.append(f"<td>{badge(v)}</td>")
            elif key in code_cols:
                cells.append(f"<td><code>{html.escape(str(v))}</code></td>")
            elif key in html_cols:
                cells.append(f"<td>{v}</td>")
            else:
                cells.append(f"<td>{html.escape(str(v))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    cls = "ff-table compact" if compact else "ff-table"
    st.markdown(f'<div class="ff-scroll"><table class="{cls}"><thead><tr>{head}</tr></thead>'
                f'<tbody>{"".join(body)}</tbody></table></div>', unsafe_allow_html=True)


def plotly_template():
    t = go.layout.Template()
    t.layout = go.Layout(
        font=dict(family="DM Sans, sans-serif", color=PLUM, size=13),
        title=dict(font=dict(family="Fraunces, serif", size=19, color=PLUM), x=0, xanchor="left"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=CREAM,
        colorway=[PLUM, PINK, "#b9a6dd", YELLOW, VIOLET, "#f5a4c4"],
        xaxis=dict(gridcolor="#efe6ef", linecolor=BORDER, zerolinecolor=BORDER, automargin=True),
        yaxis=dict(gridcolor="#efe6ef", linecolor=BORDER, zerolinecolor=BORDER, automargin=True),
        margin=dict(l=64, r=20, t=60, b=56),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    pio.templates["fallfest"] = t
    pio.templates.default = "fallfest"
    return t
