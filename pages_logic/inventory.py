"""Inventory — stock levels, reorder risk, and composition."""

import streamlit as st

from backend import data_access as db
from components import ui, charts


def render():
    ui.page_header("Inventory", "Current stock levels and reorder risk across branches")

    status = st.selectbox("Show items", ["All", "Below reorder", "OK"])
    data = db.stock(status=status)

    c1, c2, c3 = st.columns(3)
    with c1:
        ui.kpi_card("Items Shown", f"{len(data):,}")
    with c2:
        below = int((data["stock_status"] == "Below reorder").sum()) if len(data) else 0
        ui.kpi_card("Below Reorder", f"{below}", direction="up" if below else None,
                    good_when="down", delta="need restocking" if below else "")
    with c3:
        total_qty = int(data["available_qty"].sum()) if len(data) else 0
        ui.kpi_card("Available Units", f"{total_qty:,}")

    st.write("")
    left, right = st.columns([2, 1])
    with left:
        ui.section("Stock Detail")
        ui.styled_table(data, status_col="stock_status", height=380)
    with right:
        ui.section("Stock Health")
        labels, values = db.status_split("inventory")
        charts.donut(labels, values, height=300)
