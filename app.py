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
# To reorder/rename the menu, edit THIS list only. Icons are Streamlit's
# built-in Material Symbols (st.button's `icon=` param) -- native, not a
# third-party component, so the nav renders in the main document and
# follows our own CSS/dark-mode tokens instead of being stuck inside a
# custom component's iframe (which only ever sees Streamlit's static
# .streamlit/config.toml theme -- that was the "sidebar nav stays white
# in dark mode" bug with streamlit_option_menu; swapping to native
# buttons removes the iframe entirely rather than patching around it).
PAGES = {
    "Dashboard":  (":material/speed:",          dashboard.render),
    "Purchases":  (":material/shopping_cart:",  purchases.render),
    "Inventory":  (":material/inventory_2:",    inventory.render),
    "Imports":    (":material/flight:",         imports.render),
    "Logistics":  (":material/local_shipping:", logistics.render),
    "Reports":    (":material/bar_chart:",      reports.render),
    "Assistant":  (":material/chat:",           assistant.render),
}

if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"

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
    for name, (icon, _) in PAGES.items():
        is_active = st.session_state.current_page == name
        if st.button(
            name, key=f"nav_{name}", icon=icon, width="stretch",
            type="primary" if is_active else "secondary",
        ):
            st.session_state.current_page = name
            st.rerun()

# --- Route to the selected page ---
_, render_fn = PAGES[st.session_state.current_page]
render_fn()
