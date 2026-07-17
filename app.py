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

import streamlit as st
from streamlit_option_menu import option_menu

from components import ui
from components.ui import inject_styles
from components.theme import NAVY, GOLD, NAVY_DEEP

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

st.set_page_config(
    page_title="Supply Chain Intelligence",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
        f"<h2 style='color:{NAVY};margin-bottom:0;text-align:center;'>Qadri Group</h2>"
        f"<p style='color:{GOLD};font-weight:600;margin-top:0;text-align:center;'>Supply Chain Intelligence</p>",
        unsafe_allow_html=True,
    )
    choice = option_menu(
        menu_title=None,
        options=list(PAGES.keys()),
        icons=[icon for icon, _ in PAGES.values()],
        default_index=0,
        styles={
            "container": {"padding": "0", "background-color": "transparent"},
            "icon": {"color": GOLD, "font-size": "16px"},
            "nav-link": {
                "font-size": "15px",
                "color": NAVY,
                "text-align": "left",
                "margin": "2px 0",
                "--hover-color": "#EAEEF6",
            },
            "nav-link-selected": {"background-color": NAVY, "color": "white"},
        },
    )

# --- Route to the selected page ---
_, render_fn = PAGES[choice]
render_fn()
