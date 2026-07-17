"""Imports — shipments, values, and clearance status."""

import streamlit as st

from backend import data_access as db
from components import ui, charts


def render():
    ui.page_header("Imports", "Import shipments, values, and customs clearance", module="imports")

    status = st.selectbox("Show imports", db.imports_status_list())
    data = db.imports(status=status)

    c1, c2, c3 = st.columns(3)
    with c1:
        ui.kpi_card("Imports Shown", f"{len(data):,}")
    with c2:
        total = int(data["total_value_pkr"].sum()) if len(data) else 0
        ui.kpi_card("Total Value", ui.money(total))
    with c3:
        pending = int((data["current_status"] == "Under Custom Clearance").sum()) if len(data) else 0
        ui.kpi_card("Under Clearance", f"{pending}", direction="up" if pending else None,
                    good_when="down", delta="awaiting customs" if pending else "")

    st.write("")
    left, right = st.columns([2, 1])
    with left:
        ui.section("Import Shipments")
        ui.styled_table(data, status_col="current_status", height=380)
    with right:
        ui.section("Clearance Status")
        labels, values = db.status_split("imports")
        charts.donut(labels, values, height=300)
