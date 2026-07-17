"""Logistics — export shipment movements and weight."""

import streamlit as st

from backend import data_access as db
from components import ui, charts


def render():
    ui.page_header("Logistics", "Export shipments, destinations, and movements")

    kind = st.selectbox("View", ["Export"])
    data = db.logistics(kind=kind)

    c1, c2, c3 = st.columns(3)
    with c1:
        ui.kpi_card("Shipments Shown", f"{len(data):,}")
    with c2:
        weight = int(data["gross_weight_kgs"].sum()) if len(data) else 0
        ui.kpi_card("Total Gross Weight", f"{weight:,} kg")
    with c3:
        delivered = int((data["shipment_status"] == "Delivered").sum()) if len(data) else 0
        ui.kpi_card("Delivered", f"{delivered}", direction="up" if delivered else None, good_when="up")

    st.write("")
    left, right = st.columns([2, 1])
    with left:
        ui.section("Shipments")
        ui.styled_table(data, status_col="shipment_status", height=380)
    with right:
        ui.section("By Destination")
        if len(data):
            by_pod = data.groupby("pod")["gross_weight_kgs"].sum().reset_index()
            charts.ranked_bar(by_pod, "pod", "gross_weight_kgs", height=300)
        else:
            st.caption("No shipments to show.")
