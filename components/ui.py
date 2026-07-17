"""
Enterprise UI component library.

Everything visual the pages use lives here, built from the design tokens in
theme.py. Pages call these; they never write raw HTML/CSS themselves.
"""

import streamlit as st
import pandas as pd

from components import theme as T


# ======================================================================
#  GLOBAL STYLES
# ======================================================================
def inject_styles():
    st.markdown(
        f"""
        <style>
            .stApp {{ background: {T.CANVAS}; }}
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
            }}

            /* ---------- page load / element animations ---------- */
            @keyframes fadeUp {{
                from {{ opacity: 0; transform: translateY(8px); }}
                to   {{ opacity: 1; transform: translateY(0); }}
            }}

            /* ---------- page header ---------- */
            .page-head {{ margin-bottom: 4px; }}
            .page-title {{
                color:{T.NAVY}; font-size:1.75rem; font-weight:700;
                margin:0; letter-spacing:-0.01em;
            }}
            .page-sub {{ color:{T.MUTED}; font-size:0.95rem; margin:2px 0 0 0; }}
            .head-rule {{ border:none; border-top:2px solid {T.GOLD};
                          width:52px; margin:10px 0 20px 0; }}

            /* ---------- KPI card (with 3D depth + hover lift) ---------- */
            .kpi {{
                background:{T.SURFACE}; border:1px solid {T.LINE};
                border-radius:12px; padding:16px 18px;
                box-shadow:0 2px 6px rgba(31,45,78,.06), 0 1px 2px rgba(31,45,78,.04);
                transition:transform .18s ease, box-shadow .18s ease;
                height:100%;
            }}
            .kpi:hover {{
                transform: translateY(-4px);
                box-shadow:0 10px 24px rgba(31,45,78,.14), 0 3px 8px rgba(31,45,78,.08);
            }}
            .kpi-top {{ display:flex; justify-content:space-between; align-items:center; }}
            .kpi-label {{ color:{T.MUTED}; font-size:.74rem; font-weight:700;
                          text-transform:uppercase; letter-spacing:.05em; margin:0; }}
            .kpi-dot {{ width:8px; height:8px; border-radius:50%; }}
            .kpi-value {{ color:{T.NAVY}; font-size:1.9rem; font-weight:750;
                          margin:6px 0 0 0; line-height:1.05; }}
            .kpi-delta {{ font-size:.82rem; font-weight:650; margin:4px 0 0 0; }}
            .kpi-sub {{ color:{T.MUTED}; font-size:.76rem; margin:1px 0 0 0; }}

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
            .health {{ border-radius:10px; padding:14px 18px; margin-bottom:6px;
                       display:flex; align-items:center; gap:12px;
                       border:1px solid {T.LINE};
                       box-shadow:0 2px 6px rgba(31,45,78,.05); }}
            .health-icon {{ font-size:1.4rem; font-weight:800; }}
            .health-text {{ font-size:1.0rem; font-weight:600; }}

            /* ---------- alert rows (hover slide) ---------- */
            .alert {{ padding:11px 14px; border-radius:8px; margin-bottom:8px;
                      font-size:.9rem; border-left:4px solid; display:flex; gap:8px;
                      transition: transform .15s ease; }}
            .alert:hover {{ transform: translateX(3px); }}

            /* ---------- section label ---------- */
            .section {{ color:{T.NAVY}; font-size:1.05rem; font-weight:700;
                        margin:6px 0 10px 0; }}

            /* ---------- sidebar logo ---------- */
            .sidebar-logo {{ display:flex; justify-content:center; margin:4px 0 10px 0; }}
            .sidebar-logo img {{ filter: drop-shadow(0 3px 6px rgba(0,0,0,.25)); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ======================================================================
#  HEADER
# ======================================================================
def page_header(title, subtitle=""):
    st.markdown(
        f'<div class="page-head"><p class="page-title">{title}</p>'
        + (f'<p class="page-sub">{subtitle}</p>' if subtitle else "")
        + '</div><hr class="head-rule">',
        unsafe_allow_html=True,
    )


# ======================================================================
#  KPI CARD  (with trend + direction)
# ======================================================================
def kpi_card(label, value, delta=None, direction=None, good_when="down", sub=""):
    dot = T.MUTED
    delta_html = ""
    if direction in ("up", "down"):
        is_good = (direction == good_when)
        color = T.HEALTHY if is_good else T.RISK
        dot = color
        arrow = "▲" if direction == "up" else "▼"
        delta_html = f'<p class="kpi-delta" style="color:{color}">{arrow} {delta}</p>'
    elif delta:
        delta_html = f'<p class="kpi-sub">{delta}</p>'
    sub_html = f'<p class="kpi-sub">{sub}</p>' if sub else ""
    st.markdown(
        f"""
        <div class="kpi">
            <div class="kpi-top">
                <p class="kpi-label">{label}</p>
                <span class="kpi-dot" style="background:{dot}"></span>
            </div>
            <p class="kpi-value">{value}</p>
            {delta_html}{sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


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
    """Branded header block for the assistant page."""
    avatar = qadri_avatar_svg(46)
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
            <img src="{avatar}" width="46" height="46"
                 style="border-radius:10px;filter:drop-shadow(0 2px 5px rgba(0,0,0,.2));"/>
            <div>
                <p style="color:{T.NAVY};font-size:1.5rem;font-weight:750;margin:0;line-height:1.1;">
                    {ASSISTANT_NAME}</p>
                <p style="color:{T.MUTED};font-size:0.9rem;margin:2px 0 0 0;">
                    Your Qadri Group supply chain assistant</p>
            </div>
            <span style="margin-left:auto;display:flex;align-items:center;gap:6px;
                         background:{T.HEALTHY_BG};color:{T.HEALTHY};padding:5px 12px;
                         border-radius:20px;font-size:0.8rem;font-weight:650;">
                <span style="width:8px;height:8px;border-radius:50%;background:{T.HEALTHY};
                             display:inline-block;"></span> Online
            </span>
        </div>
        <hr class="head-rule">
        """,
        unsafe_allow_html=True,
    )
