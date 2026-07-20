"""
Supply Chain Intelligence System — frontend entry point.

This file does ONLY two things:
  1. sets up the page + navigation
  2. routes to the chosen page's render() function

It contains no business logic and no data access. Each page lives in
pages_logic/ and each fetches its data through backend/data_access.py.

Run locally:      streamlit run app.py
Run on office LAN: streamlit run app.py --server.address 0.0.0.0
"""

import os

import streamlit as st
from streamlit_option_menu import option_menu

from components import ui
from components.ui import inject_styles
from components import theme as T

# Page modules
from pages_logic import (
    dashboard,
    purchases,
    inventory,
    imports,
    logistics,
    reports,
    assistant,
)

_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "qadri_logo_transparent.png")

st.set_page_config(
    page_title="Supply Chain Intelligence",
    page_icon=_LOGO_PATH if os.path.exists(_LOGO_PATH) else "📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Streamlit only imports theme.py once per server process -- reruns don't
# re-execute it -- so switching palettes can't rely on re-import. Instead
# set_mode() reassigns theme.py's module globals in place; this MUST run
# before inject_styles() and before any page reads a T.XXX color, since
# every other file resolves T.XXX as a plain attribute lookup at call time.
T.set_mode(st.session_state.get("dark_mode", False))
inject_styles()

# --- Navigation config (single source of truth) ---
# To reorder/rename the menu, edit THIS list only.
PAGES = {
    "Dashboard":  ("speedometer2", dashboard.render),
    "Purchases":  ("cart",          purchases.render),
    "Inventory":  ("box-seam",      inventory.render),
    "Imports":    ("airplane",      imports.render),
    "Logistics":  ("truck",         logistics.render),
    "Reports":    ("file-earmark-bar-graph", reports.render),
    "Assistant":  ("chat-dots",     assistant.render),
}

with st.sidebar:
    ui.sidebar_logo()
    st.markdown(
        f"<h2 style='color:{T.NAVY};margin-bottom:0;text-align:center;font-family:{T.DISPLAY_FONT_STACK};'>Qadri Group</h2>"
        f"<p style='color:{T.GOLD};font-weight:600;margin-top:0;text-align:center;'>Supply Chain Intelligence</p>",
        unsafe_allow_html=True,
    )
    st.write("")
    tcol1, tcol2 = st.columns([1, 4])
    with tcol1:
        st.write("🌙" if st.session_state.get("dark_mode") else "☀️")
    with tcol2:
        st.toggle("Dark mode", key="dark_mode")
    st.write("")
    choice = option_menu(
        menu_title=None,
        options=list(PAGES.keys()),
        icons=[icon for icon, _ in PAGES.values()],
        default_index=0,
        styles={
            "container": {"padding": "0", "background-color": "transparent"},
            "icon": {"color": T.MUTED, "font-size": "16px"},
            "nav-link": {
                "font-size": "15px",
                "color": T.NAVY,
                "text-align": "left",
                "margin": "3px 0",
                "border-radius": "10px",
                "--hover-color": T.BRAND_SOFT,
            },
            "nav-link-selected": {
                "background": T.GRADIENT_BRAND,
                "color": "white",
                "border-radius": "10px",
                "box-shadow": "0 4px 12px rgba(79,70,229,.28)",
            },
        },
    )

# --- Route to the selected page ---
_, render_fn = PAGES[choice]
render_fn()
