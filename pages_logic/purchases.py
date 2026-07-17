"""Purchases — order tracking with intent filters, KPIs, and status table."""

import streamlit as st

from backend import data_access as db
from components import ui, charts


def render():
    ui.page_header("Purchases", "Track purchase orders, suppliers, and delivery status", module="purchases")

    f1, f2 = st.columns(2)
    with f1:
        status = st.selectbox("Show orders", ["All", "Pending", "Completed", "Delayed"])
    with f2:
        supplier = st.selectbox("Supplier", db.supplier_list())

    data = db.purchases(status=status, supplier=supplier)

    c1, c2, c3 = st.columns(3)
    with c1:
        ui.kpi_card("Orders Shown", f"{len(data):,}")
    with c2:
        total = int(data["amount"].sum()) if len(data) else 0
        ui.kpi_card("Total Value", ui.money(total))
    with c3:
        delayed = int((data["status"] == "Delayed").sum()) if len(data) else 0
        ui.kpi_card("Delayed", f"{delayed}", direction="up" if delayed else None, good_when="down",
                    delta="in current view" if delayed else "")

    st.write("")
    left, right = st.columns([2, 1])
    with left:
        ui.section("Purchase Orders")
        ui.styled_table(data, status_col="status", height=380)
    with right:
        ui.section("Status Breakdown")
        if len(data):
            counts = data["status"].value_counts()
            charts.donut(list(counts.index), list(counts.values), height=300)
        else:
            st.caption("No orders match the current filter.")
