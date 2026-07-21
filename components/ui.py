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
    st.markdown(f'<link href="{T.DISPLAY_FONT_URL}" rel="stylesheet">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <style>
            .stApp {{ background: {T.CANVAS}; }}
            .block-container {{ padding-top: 2rem; padding-bottom: 2rem; max-width: 1400px;
                                animation: fadeUp .5s ease; }}
            html, body, [class*="css"] {{ font-family: {T.FONT_STACK}; }}

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
                min-width: 280px !important;
                max-width: 280px !important;
                transform: none !important;
                visibility: visible !important;
                background: {T.SIDEBAR_BG} !important;
                border-right: 1px solid {T.LINE};
            }}
            /* Streamlit's sidebar has nested wrapper divs below [data-testid=
               "stSidebar"] itself (a resizer div, then stSidebarContent, then
               a .block-container) -- each can carry its own background from
               Streamlit's static native theme (.streamlit/config.toml), which
               paints over the dark background above since a child's own
               background always covers its parent's. Clearing every known
               nesting level, not just the direct child, is what actually
               fixes "the sidebar stays white in dark mode." */
            [data-testid="stSidebar"] > div,
            [data-testid="stSidebar"] [data-testid="stSidebarContent"],
            [data-testid="stSidebar"] [data-testid="stSidebarUserContent"],
            [data-testid="stSidebar"] .block-container {{
                background: transparent !important;
            }}

            /* ---------- page load / element animations ---------- */
            @keyframes fadeUp {{
                from {{ opacity: 0; transform: translateY(8px); }}
                to   {{ opacity: 1; transform: translateY(0); }}
            }}

            /* ---------- page header: restrained white banner + accent badge ---------- */
            .page-banner {{
                position:relative; display:flex; align-items:center; justify-content:space-between;
                gap:20px; background:{T.SURFACE}; border:1px solid {T.LINE}; border-radius:18px;
                padding:22px 28px; margin-bottom:24px;
                box-shadow:0 2px 10px rgba(31,45,78,.05);
                animation: fadeUp .5s ease;
            }}
            .page-banner-badge {{
                flex:none; width:60px; height:60px; border-radius:16px;
                display:flex; align-items:center; justify-content:center;
            }}
            .page-banner-badge svg {{ width:28px; height:28px; }}
            .page-title {{
                font-family:{T.DISPLAY_FONT_STACK}; color:{T.NAVY}; font-size:1.65rem; font-weight:800;
                margin:0; letter-spacing:-0.02em;
            }}
            .page-sub {{ color:{T.MUTED}; font-size:0.92rem; margin:4px 0 0 0; }}

            /* ---------- KPI card: white surface, semantic accent border + icon chip ---------- */
            .kpi {{
                position:relative; background:{T.SURFACE}; border:1px solid {T.LINE};
                border-left:3px solid transparent; border-radius:16px; padding:18px;
                box-shadow:0 2px 10px rgba(31,45,78,.05);
                transition:transform .18s ease, box-shadow .18s ease;
                height:100%;
            }}
            .kpi:hover {{
                transform: translateY(-3px);
                box-shadow:0 10px 24px rgba(31,45,78,.10);
            }}
            .kpi-top {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }}
            .kpi-icon-chip {{
                width:36px; height:36px; border-radius:11px; flex:none;
                display:flex; align-items:center; justify-content:center;
            }}
            .kpi-icon-chip svg {{ width:18px; height:18px; }}
            .kpi-pill {{ font-size:.72rem; font-weight:700; padding:3px 10px; border-radius:20px; }}
            .kpi-label {{ color:{T.MUTED}; font-size:.76rem; font-weight:650; margin:0; }}
            .kpi-value {{
                font-family:{T.DISPLAY_FONT_STACK}; color:{T.NAVY}; font-size:1.85rem; font-weight:800;
                margin:4px 0 0 0; line-height:1.05;
            }}
            .kpi-sub {{ color:{T.MUTED}; font-size:.76rem; margin:4px 0 0 0; }}
            .kpi-spark {{ display:block; width:100%; height:26px; margin-top:10px; }}

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
                       box-shadow:0 2px 8px rgba(31,45,78,.04); }}
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

            /* ---------- chatbot popover trigger (floating, landing page) ----------
               st.container(key="chat_fab") emits a stable .st-key-chat_fab class —
               the supported way to target a specific block of real widgets with
               custom CSS (hand-written <div> wrappers don't work: Streamlit
               widgets never render literally nested inside markdown HTML). ---------- */
            .st-key-chat_fab {{
                position:fixed; bottom:28px; right:32px; z-index:999; width:auto;
            }}
            /* data-testid="stPopoverButton" is set directly on the trigger's
               <button> element (not a wrapping div around a nested button,
               which the previous "[data-testid=stPopoverButton] button"
               selector assumed) -- so that rule never matched anything and
               the trigger fell back to Streamlit's plain secondary-button
               style, showing as a white pill that only got a faint tint on
               Streamlit's own default hover. Matching both possible shapes
               here so this keeps working regardless of the exact DOM. */
            .st-key-chat_fab [data-testid="stPopoverButton"],
            .st-key-chat_fab [data-testid="stPopoverButton"] button {{
                background:{T.GRADIENT_BRAND} !important; color:white !important;
                border:none !important; border-radius:999px !important;
                padding:12px 22px !important; font-weight:700 !important;
                box-shadow:0 8px 24px rgba(79,70,229,.4) !important;
                transition: transform .15s ease, box-shadow .15s ease;
            }}
            .st-key-chat_fab [data-testid="stPopoverButton"]:hover,
            .st-key-chat_fab [data-testid="stPopoverButton"] button:hover {{
                transform: translateY(-2px);
                box-shadow:0 12px 30px rgba(79,70,229,.5) !important;
            }}

            /* ---------- chat popover panel + bubbles (shared: Assistant page + FAB) ---------- */
            div[data-testid="stPopoverBody"] {{
                background:{T.SURFACE} !important; border:1px solid {T.LINE} !important;
                border-radius:16px !important; box-shadow:0 16px 40px rgba(0,0,0,.18) !important;
            }}
            [data-testid="stChatMessage"] {{
                background:{T.CANVAS_ALT}; border-radius:14px; border:1px solid {T.LINE};
            }}
            [data-testid="stChatInput"] textarea {{
                background:{T.SURFACE} !important; color:{T.INK} !important;
            }}
            [data-testid="stChatInput"] {{
                border:1px solid {T.LINE} !important; border-radius:14px !important;
                background:{T.SURFACE} !important;
            }}

            /* ---------- body text + native widgets: mode-aware ----------
               Broad pass so text stays readable and the most common inputs
               (text/select/multiselect/slider/expander/tabs/buttons) follow
               the toggle. st.dataframe renders its grid on <canvas> — cell
               colors DO follow our styled_table()/status_colors() (they're
               set explicitly per-row), but the grid's own chrome (header
               row, scrollbar) is Streamlit's native theme engine and isn't
               reachable from CSS; a known, minor seam in dark mode. ---------- */
            .stApp, .stApp p, .stApp span, .stApp label, [data-testid="stMarkdownContainer"] {{
                color:{T.INK};
            }}
            [data-testid="stCaptionContainer"] {{ color:{T.MUTED} !important; }}
            [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
            [data-testid="stNumberInput"] input {{
                background:{T.SURFACE} !important; color:{T.INK} !important; border-color:{T.LINE} !important;
            }}
            [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
            [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {{
                background:{T.SURFACE} !important; color:{T.INK} !important; border-color:{T.LINE} !important;
            }}
            [data-testid="stExpander"] {{
                background:{T.SURFACE} !important; border:1px solid {T.LINE} !important; border-radius:12px !important;
            }}
            [data-testid="stTabs"] [data-baseweb="tab"] {{ color:{T.MUTED}; }}
            [data-testid="stTabs"] [aria-selected="true"] {{ color:{T.BRAND}; }}
            /* scoped to secondary buttons only -- primary buttons (the
               active sidebar nav item) keep Streamlit's own primaryColor
               styling, which is mode-independent (BRAND is a fixed accent,
               not a light/dark token), so overriding it here would wipe
               out the "selected page" highlight. */
            [data-testid="stBaseButton-secondary"], [data-testid="stFormSubmitButton"] button,
            .stDownloadButton > button {{
                background:{T.SURFACE}; color:{T.INK}; border:1px solid {T.LINE};
            }}
            [data-testid="stDataFrame"] {{ border:1px solid {T.LINE}; border-radius:10px; overflow:hidden; }}

            /* ---------- sidebar nav (native st.button, one per page) ---------- */
            [data-testid="stSidebar"] .stButton > button {{
                justify-content:flex-start; text-align:left; border-radius:10px;
                font-weight:600; margin:2px 0; padding:8px 14px;
            }}
            [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {{
                background:transparent !important; border:1px solid transparent !important; color:{T.NAVY} !important;
            }}
            [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {{
                background:{T.BRAND_SOFT} !important; color:{T.BRAND} !important;
            }}
            [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {{
                background:{T.GRADIENT_BRAND} !important; border:none !important;
                box-shadow:0 4px 12px rgba(79,70,229,.28);
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ======================================================================
#  HEADER  (restrained white banner, module accent shows up only in the badge)
# ======================================================================
def page_header(title, subtitle="", module="dashboard"):
    accent, soft = T.module_colors(module)
    icon_path = T.MODULE_ICONS.get(module, T.MODULE_ICONS["dashboard"])
    _html_block(f"""
        <div class="page-banner">
            <div class="page-banner-text">
                <p class="page-title">{title}</p>
                {f'<p class="page-sub">{subtitle}</p>' if subtitle else ""}
            </div>
            <div class="page-banner-badge" style="background:{soft};color:{accent};">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{icon_path}</svg>
            </div>
        </div>
        """)


def hero_mark(image_uri, title, subtitle, size=64):
    """Centered mark + headline for a hero/empty state (e.g. the Assistant
    page's search-homepage-style landing). Caller is responsible for column
    layout (`st.columns([1, 2, 1])`) to constrain width — this only renders
    the centered content itself.
    """
    _html_block(f"""
        <div style="text-align:center;">
            <img src="{image_uri}" width="{size}" height="{size}"
                 style="border-radius:18px;box-shadow:0 10px 28px rgba(79,70,229,.28);margin-bottom:18px;"/>
            <p style="font-family:{T.DISPLAY_FONT_STACK};font-size:1.9rem;font-weight:800;
                      color:{T.NAVY};margin:0 0 8px 0;letter-spacing:-0.02em;">{title}</p>
            <p style="color:{T.MUTED};font-size:1rem;margin:0 0 26px 0;">{subtitle}</p>
        </div>
        """)


# ======================================================================
#  KPI CARD  (white surface, semantic accent chip/border + optional sparkline)
# ======================================================================
_ICON_CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
_ICON_ALERT = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
               'stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"/><path d="M12 17h.01"/>'
               '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/></svg>')
_ICON_DOT = '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="6"/></svg>'


def _sparkline_svg(values, color, width=200, height=26):
    """A minimal, dependency-free inline sparkline — no chart library needed
    for a 4-8-point trend line inside a KPI card. Returns "" if there isn't
    enough real data to draw a line (never fabricates points).
    """
    values = [v for v in values if v is not None]
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    n = len(values)
    pts = [f"{(i / (n - 1)) * width:.1f},{height - 2 - ((v - lo) / span) * (height - 4):.1f}"
           for i, v in enumerate(values)]
    return (f'<svg class="kpi-spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none">'
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def kpi_card(label, value, delta=None, direction=None, good_when="down", sub="", spark=None):
    """A restrained KPI card: white surface, with the R/A/G semantic signal
    carried by a small icon chip + a thin left-edge accent border rather
    than a full-card color wash. `spark`, if given, is a list of real
    historical values (e.g. weekly totals) rendered as a tiny trend line —
    omitted entirely when there's no real series behind a number.
    """
    pill_html = ""
    if direction in ("up", "down"):
        is_good = (direction == good_when)
        ink, icon = (T.HEALTHY, _ICON_CHECK) if is_good else (T.RISK, _ICON_ALERT)
        arrow = "▲" if direction == "up" else "▼"
        pill_html = f'<span class="kpi-pill" style="background:{T.CANVAS_ALT};color:{ink};">{arrow} {delta}</span>'
        delta_sub_html = ""
    else:
        ink, icon = T.BRAND, _ICON_DOT
        delta_sub_html = f'<p class="kpi-sub">{delta}</p>' if delta else ""
    sub_html = f'<p class="kpi-sub">{sub}</p>' if sub else ""
    spark_html = _sparkline_svg(spark, ink) if spark else ""
    _html_block(f"""
        <div class="kpi" style="border-left-color:{ink};">
            <div class="kpi-top">
                <div class="kpi-icon-chip" style="background:{ink}1A;color:{ink};">{icon}</div>
                {pill_html}
            </div>
            <p class="kpi-value">{value}</p>
            <p class="kpi-label">{label}</p>
            {delta_sub_html}{sub_html}{spark_html}
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
            # background-color alone left text at st.dataframe's own default
            # (static, theme-driven) color -- fine against the light-mode
            # pastel backgrounds, but against the dark-mode backgrounds that
            # default stayed dark too, reading as barely-visible ghost text.
            # Pinning color explicitly makes every row legible in both modes.
            return [f"background-color:{bg};color:{T.INK}"] * len(row)
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
    """Branded header block for the assistant page — same restrained-banner
    system as every other page (module="assistant"), with the avatar and
    the online badge laid over it.
    """
    avatar = qadri_avatar_svg(46)
    accent, soft = T.module_colors("assistant")
    icon_path = T.MODULE_ICONS["assistant"]
    _html_block(f"""
        <div class="page-banner">
            <div class="page-banner-text" style="display:flex;align-items:center;gap:14px;">
                <img src="{avatar}" width="46" height="46" style="border-radius:10px;"/>
                <div>
                    <p class="page-title" style="font-size:1.4rem;line-height:1.1;">{ASSISTANT_NAME}</p>
                    <p class="page-sub">Your Qadri Group supply chain assistant</p>
                </div>
                <span style="display:flex;align-items:center;gap:6px;
                             background:{T.HEALTHY_BG};color:{T.HEALTHY};padding:5px 12px;
                             border-radius:20px;font-size:0.8rem;font-weight:650;">
                    <span style="width:8px;height:8px;border-radius:50%;background:{T.HEALTHY};
                                 display:inline-block;"></span> Online
                </span>
            </div>
            <div class="page-banner-badge" style="background:{soft};color:{accent};">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{icon_path}</svg>
            </div>
        </div>
        """)


def chat_popover(on_ask, history_limit=6):
    """A small floating chat widget, meant for the landing page — a quick
    question without leaving the dashboard. Shares the same conversation
    history as the full Assistant page (st.session_state.chat), so it reads
    as one continuous assistant rather than two separate bots.

    Stays presentation-only like the rest of this module: `on_ask(question)`
    is supplied by the calling page (which already imports backend.data_access)
    and must return {understood, answer, table}.
    """
    if "chat" not in st.session_state:
        st.session_state.chat = []

    avatar = qadri_avatar_svg(30)
    with st.container(key="chat_fab"):
        with st.popover("💬 Ask QadriBot", width=380):
            _html_block(f"""
                <div style="margin:-1rem -1rem 12px -1rem; padding:16px 18px;
                            background:{T.GRADIENT_BRAND}; border-radius:12px 12px 0 0;
                            display:flex; align-items:center; gap:10px;">
                    <img src="{avatar}" width="30" height="30" style="border-radius:8px;"/>
                    <div>
                        <p style="margin:0;color:white;font-weight:800;font-size:1rem;
                                  font-family:{T.DISPLAY_FONT_STACK};line-height:1.1;">{ASSISTANT_NAME}</p>
                        <p style="margin:0;color:rgba(255,255,255,.85);font-size:.74rem;">
                            Ask about your supply chain</p>
                    </div>
                </div>
                """)
            history = st.session_state.chat[-history_limit:]
            if not history:
                st.caption("Try: \"Which purchase orders are delayed?\"")
            for turn in history:
                with st.chat_message(turn["role"], avatar=avatar if turn["role"] == "assistant" else None):
                    st.markdown(turn["content"])
            if prompt := st.chat_input("Message QadriBot...", key="fab_chat_input"):
                st.session_state.chat.append({"role": "user", "content": prompt})
                result = on_ask(prompt)
                answer = f"*I understood: {result['understood']}*\n\n{result['answer']}"
                st.session_state.chat.append(
                    {"role": "assistant", "content": answer, "table": result.get("table")}
                )
                st.rerun()
