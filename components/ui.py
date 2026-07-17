"""
Enterprise UI component library.

Everything visual the pages use lives here, built from the design tokens in
theme.py. Pages call these; they never write raw HTML/CSS themselves.
"""

import streamlit as st
import pandas as pd

from components import theme as T


def _html_block(s):
    """st.markdown(unsafe_allow_html=True) drops out of raw-HTML mode at the
    first blank (or whitespace-only) line inside a multi-line HTML block —
    everything after gets escaped and shown as literal text instead of
    rendered. Conditional f-string fragments (e.g. an optional <p> that's
    "" when there's nothing to show) leave exactly that kind of blank line,
    so every multi-line HTML block in this file is routed through here to
    strip them before they reach Streamlit.
    """
    st.markdown("\n".join(line for line in s.splitlines() if line.strip()),
                unsafe_allow_html=True)


# ======================================================================
#  GLOBAL STYLES
# ======================================================================
def inject_styles():
    st.markdown(
        f"""
        <style>
            .stApp {{ background: {T.GRADIENT_CANVAS}; background-attachment: fixed; }}
            .block-container {{ padding-top: 2.4rem; padding-bottom: 2rem; max-width: 1400px;
                                animation: fadeUp .5s ease; }}

            /* ---------- hide the Deploy button and main menu ---------- */
            [data-testid="stToolbar"] {{ display: none !important; }}
            #MainMenu {{ display: none !important; }}
            footer {{ visibility: hidden; }}
            /* Remove the now-empty header strip. Safe because the sidebar is
               locked open below and no longer relies on the header toggle. */
            header[data-testid="stHeader"] {{ display: none !important; }}

            /* ---------- LOCK the sidebar permanently open ----------
               Hiding the collapse control means the sidebar can never be
               closed, so navigation can never get stuck. This is the safest
               behaviour for the management demo. ---------- */
            [data-testid="stSidebarCollapseButton"] {{ display: none !important; }}
            [data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}
            [data-testid="stExpandSidebarButton"] {{ display: none !important; }}
            [data-testid="stSidebar"] {{
                min-width: 300px !important;
                max-width: 300px !important;
                transform: none !important;
                visibility: visible !important;
                background: {T.GRADIENT_SIDEBAR} !important;
                box-shadow: 4px 0 24px rgba(22,34,60,.18);
            }}
            [data-testid="stSidebar"] > div {{ background: transparent; }}

            /* ---------- page load / element animations ---------- */
            @keyframes fadeUp {{
                from {{ opacity: 0; transform: translateY(8px); }}
                to   {{ opacity: 1; transform: translateY(0); }}
            }}

            /* ---------- page header: full gradient banner + watermark icon ---------- */
            .page-banner {{
                position:relative; overflow:hidden; border-radius:20px;
                padding:28px 32px; margin-bottom:24px;
                box-shadow:0 12px 32px rgba(31,45,78,.20);
                animation: fadeUp .5s ease;
            }}
            .page-banner-icon {{
                position:absolute; right:-18px; top:50%; transform:translateY(-50%);
                width:160px; height:160px; opacity:.15; pointer-events:none;
            }}
            .page-banner-text {{ position:relative; z-index:1; }}
            .page-title {{
                color:white; font-size:1.85rem; font-weight:750;
                margin:0; letter-spacing:-0.01em;
            }}
            .page-sub {{ color:rgba(255,255,255,.88); font-size:0.95rem; margin:4px 0 0 0; }}

            /* ---------- KPI card (semantic pastel tint + icon chip + trend pill) ---------- */
            .kpi {{
                position:relative;
                border-radius:18px; padding:18px;
                box-shadow:0 4px 14px rgba(31,45,78,.08);
                transition:transform .18s ease, box-shadow .18s ease;
                height:100%;
            }}
            .kpi:hover {{
                transform: translateY(-4px);
                box-shadow:0 14px 30px rgba(31,45,78,.16);
            }}
            .kpi-top {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }}
            .kpi-icon-chip {{
                width:38px; height:38px; border-radius:12px; flex:none;
                display:flex; align-items:center; justify-content:center;
            }}
            .kpi-icon-chip svg {{ width:19px; height:19px; }}
            .kpi-pill {{ font-size:.72rem; font-weight:700; padding:3px 10px; border-radius:20px; }}
            .kpi-label {{ font-size:.78rem; font-weight:650; margin:0; }}
            .kpi-value {{ color:{T.NAVY}; font-size:1.9rem; font-weight:750;
                          margin:4px 0 0 0; line-height:1.05; }}
            .kpi-sub {{ color:{T.MUTED}; font-size:.76rem; margin:4px 0 0 0; }}

            /* ---------- buttons: subtle transition + lift ---------- */
            .stButton > button, .stDownloadButton > button {{
                transition: transform .15s ease, box-shadow .15s ease, background .15s ease;
                border-radius: 8px;
            }}
            .stButton > button:hover, .stDownloadButton > button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 16px rgba(31,45,78,.12);
            }}

            /* ---------- status badge ---------- */
            .badge {{ display:inline-block; padding:3px 10px; border-radius:20px;
                      font-size:.76rem; font-weight:650; }}

            /* ---------- health banner ---------- */
            .health {{ border-radius:12px; padding:14px 18px; margin-bottom:6px;
                       display:flex; align-items:center; gap:12px;
                       border:1px solid {T.LINE};
                       box-shadow:0 2px 10px rgba(79,70,229,.06); }}
            .health-icon {{ font-size:1.4rem; font-weight:800; }}
            .health-text {{ font-size:1.0rem; font-weight:600; }}

            /* ---------- alert rows (hover slide) ---------- */
            .alert {{ padding:11px 14px; border-radius:10px; margin-bottom:8px;
                      font-size:.9rem; border-left:4px solid; display:flex; gap:8px;
                      transition: transform .15s ease; }}
            .alert:hover {{ transform: translateX(3px); }}

            /* ---------- section label ---------- */
            .section {{ position:relative; color:{T.NAVY}; font-size:1.05rem; font-weight:700;
                        margin:6px 0 10px 0; padding-left:12px; }}
            .section::before {{
                content:""; position:absolute; left:0; top:2px; bottom:2px; width:4px;
                border-radius:3px; background:{T.GRADIENT_BRAND};
            }}

            /* ---------- sidebar logo ---------- */
            .sidebar-logo {{ display:flex; justify-content:center; margin:4px 0 10px 0; }}
            .sidebar-logo img {{ filter: drop-shadow(0 3px 6px rgba(0,0,0,.25)); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ======================================================================
#  HEADER  (full gradient banner, distinct per module)
# ======================================================================
def page_header(title, subtitle="", module="dashboard"):
    mod = T.MODULES.get(module, T.MODULES["dashboard"])
    icon_path = T.MODULE_ICONS.get(module, T.MODULE_ICONS["dashboard"])
    _html_block(f"""
        <div class="page-banner" style="background:{mod['gradient']};">
            <svg class="page-banner-icon" viewBox="0 0 24 24" fill="none" stroke="white"
                 stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round">{icon_path}</svg>
            <div class="page-banner-text">
                <p class="page-title">{title}</p>
                {f'<p class="page-sub">{subtitle}</p>' if subtitle else ""}
            </div>
        </div>
        """)


# ======================================================================
#  KPI CARD  (semantic pastel tint + icon chip + trend pill)
# ======================================================================
_ICON_CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
_ICON_ALERT = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
               'stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"/><path d="M12 17h.01"/>'
               '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/></svg>')
_ICON_DOT = '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="6"/></svg>'


def kpi_card(label, value, delta=None, direction=None, good_when="down", sub=""):
    """A KPI card whose background tint reflects whether the number is
    actually good or bad — same R/A/G discipline as everywhere else in the
    app, just applied to the whole card instead of a small dot, so it reads
    at a glance the way the reference dashboards do.
    """
    pill_html = ""
    if direction in ("up", "down"):
        is_good = (direction == good_when)
        tint, ink, icon = (T.HEALTHY_BG, T.HEALTHY, _ICON_CHECK) if is_good else (T.RISK_BG, T.RISK, _ICON_ALERT)
        arrow = "▲" if direction == "up" else "▼"
        pill_html = f'<span class="kpi-pill" style="background:rgba(255,255,255,.65);color:{ink};">{arrow} {delta}</span>'
        delta_sub_html = ""
    else:
        tint, ink, icon = T.BRAND_SOFT, T.BRAND, _ICON_DOT
        delta_sub_html = f'<p class="kpi-sub">{delta}</p>' if delta else ""
    sub_html = f'<p class="kpi-sub">{sub}</p>' if sub else ""
    _html_block(f"""
        <div class="kpi" style="background:{tint};">
            <div class="kpi-top">
                <div class="kpi-icon-chip" style="background:{ink};color:white;">{icon}</div>
                {pill_html}
            </div>
            <p class="kpi-value">{value}</p>
            <p class="kpi-label" style="color:{ink};">{label}</p>
            {delta_sub_html}{sub_html}
        </div>
        """)


# ======================================================================
#  HEALTH BANNER + ALERTS
# ======================================================================
def health_banner(level, message):
    icon = {"healthy": "✓", "watch": "!", "risk": "▲"}.get(level, "•")
    fg, bg = {
        "healthy": (T.HEALTHY, T.HEALTHY_BG),
        "watch":   (T.WATCH, T.WATCH_BG),
        "risk":    (T.RISK, T.RISK_BG),
    }.get(level, (T.INFO, T.INFO_BG))
    st.markdown(
        f'<div class="health" style="background:{bg};border-color:{fg}33">'
        f'<span class="health-icon" style="color:{fg}">{icon}</span>'
        f'<span class="health-text" style="color:{fg}">{message}</span></div>',
        unsafe_allow_html=True,
    )


def alert_row(level, message):
    fg, bg = {
        "high":   (T.RISK, T.RISK_BG),
        "medium": (T.WATCH, T.WATCH_BG),
        "low":    (T.INFO, T.INFO_BG),
    }.get(level, (T.INFO, T.INFO_BG))
    st.markdown(
        f'<div class="alert" style="background:{bg};border-color:{fg};color:{fg}">'
        f'<b>•</b><span>{message}</span></div>',
        unsafe_allow_html=True,
    )


def section(label):
    st.markdown(f'<p class="section">{label}</p>', unsafe_allow_html=True)


def badge(label):
    fg, bg = T.status_colors(label)
    return f'<span class="badge" style="background:{bg};color:{fg}">{label}</span>'


# ======================================================================
#  STYLED TABLE
# ======================================================================
def styled_table(df, status_col=None, height=None):
    if status_col and status_col in df.columns:
        def _row_style(row):
            fg, bg = T.status_colors(row[status_col])
            return [f"background-color:{bg}"] * len(row)
        styler = df.style.apply(_row_style, axis=1)
        st.dataframe(styler, width="stretch", hide_index=True, height=height)
    else:
        st.dataframe(df, width="stretch", hide_index=True, height=height)


# ======================================================================
#  FORMAT HELPERS
# ======================================================================
def money(value):
    if value >= 1_000_000:
        return f"PKR {value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"PKR {value/1_000:.0f}K"
    return f"PKR {value:,.0f}"


# ======================================================================
#  BRANDING  (real Qadri logo)
# ======================================================================
import os
import base64 as _b64

ASSISTANT_NAME = "QadriBot"

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")


def _logo_data_uri(transparent=True):
    """Load the Qadri logo from assets/ as a base64 data-URI (cached)."""
    if not hasattr(_logo_data_uri, "_cache"):
        _logo_data_uri._cache = {}
    if transparent in _logo_data_uri._cache:
        return _logo_data_uri._cache[transparent]

    fname = "qadri_logo_transparent.png" if transparent else "qadri_logo.png"
    path = os.path.join(_ASSETS, fname)
    uri = ""
    if os.path.exists(path):
        with open(path, "rb") as f:
            uri = "data:image/png;base64," + _b64.b64encode(f.read()).decode()
    _logo_data_uri._cache[transparent] = uri
    return uri


def qadri_avatar_svg(size=40):
    """The Qadri logo as the assistant avatar (falls back to a monogram)."""
    uri = _logo_data_uri(transparent=True)
    if uri:
        return uri
    # fallback monogram if the image is missing
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 40 40">
      <rect width="40" height="40" rx="10" fill="{T.NAVY}"/>
      <circle cx="20" cy="19" r="10" fill="none" stroke="{T.GOLD}" stroke-width="3"/>
      <line x1="24" y1="23" x2="30" y2="29" stroke="{T.GOLD}" stroke-width="3" stroke-linecap="round"/>
    </svg>'''
    return "data:image/svg+xml;base64," + _b64.b64encode(svg.encode()).decode()


def sidebar_logo():
    """Render the Qadri logo at the top of the sidebar."""
    uri = _logo_data_uri(transparent=True)
    if uri:
        st.markdown(
            f'<div class="sidebar-logo"><img src="{uri}" width="120"/></div>',
            unsafe_allow_html=True,
        )


def assistant_header():
    """Branded header block for the assistant page — same gradient-banner
    system as every other page (module="assistant"), with the avatar and
    the online badge laid over it.
    """
    avatar = qadri_avatar_svg(46)
    mod = T.MODULES["assistant"]
    icon_path = T.MODULE_ICONS["assistant"]
    _html_block(f"""
        <div class="page-banner" style="background:{mod['gradient']}; padding:20px 28px;">
            <svg class="page-banner-icon" viewBox="0 0 24 24" fill="none" stroke="white"
                 stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round">{icon_path}</svg>
            <div class="page-banner-text" style="display:flex;align-items:center;gap:14px;">
                <img src="{avatar}" width="46" height="46"
                     style="border-radius:10px;filter:drop-shadow(0 2px 5px rgba(0,0,0,.25));"/>
                <div>
                    <p class="page-title" style="font-size:1.5rem;line-height:1.1;">{ASSISTANT_NAME}</p>
                    <p class="page-sub">Your Qadri Group supply chain assistant</p>
                </div>
                <span style="margin-left:auto;display:flex;align-items:center;gap:6px;
                             background:rgba(255,255,255,.25);color:white;padding:5px 12px;
                             border-radius:20px;font-size:0.8rem;font-weight:650;">
                    <span style="width:8px;height:8px;border-radius:50%;background:#4ADE80;
                                 display:inline-block;"></span> Online
                </span>
            </div>
        </div>
        """)
