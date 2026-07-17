"""Logistics — export and import shipment movements.

Export view  -> public.exports
Import view  -> public.shipment_details

Both come back from db.logistics() with a derived `status` column, so the
table colour-codes the same way for either view. Columns shown are the REAL
columns from the database (adapted to the data, not the other way around).
"""

import streamlit as st

from backend import data_access as db
from components import ui, charts


def render():
    ui.page_header("Logistics", "Export and import shipments, ports, and movements")

    kind = st.selectbox("View", ["Export", "Import"])
    data = db.logistics(kind=kind)

    c1, c2, c3 = st.columns(3)

    if kind == "Export":
        with c1:
            ui.kpi_card("Shipments Shown", f"{len(data):,}")
        with c2:
            sailed = int(data["sailing_date"].notna().sum()) if len(data) else 0
            ui.kpi_card("Sailed", f"{sailed:,}")
        with c3:
            handed = int((data["status"] == "Completed").sum()) if len(data) else 0
            ui.kpi_card("Handed Over", f"{handed:,}",
                        direction="up" if handed else None, good_when="up")
    else:  # Import
        with c1:
            ui.kpi_card("Shipments Shown", f"{len(data):,}")
        with c2:
            cleared = int((data["status"] == "Cleared").sum()) if len(data) else 0
            ui.kpi_card("Cleared", f"{cleared:,}",
                        direction="up" if cleared else None, good_when="up")
        with c3:
            in_transit = int((data["status"] == "In Transit").sum()) if len(data) else 0
            ui.kpi_card("In Transit", f"{in_transit:,}")

    st.write("")
    left, right = st.columns([2, 1])

    with left:
        ui.section("Shipments")
        ui.styled_table(data, status_col="status", height=380)

    with right:
        if kind == "Export":
            ui.section("By Shipping Agent")
            cat = "shipping_agent"
        else:
            ui.section("By Destination Port")
            cat = "pod"

        if len(data):
            grp = (
                data.assign(**{cat: data[cat].fillna("Unknown")})
                    .groupby(cat).size()
                    .reset_index(name="shipments")
                    .sort_values("shipments", ascending=False)
                    .head(10)
            )
            charts.ranked_bar(grp, cat, "shipments", height=300)
        else:
            st.caption("No shipments to show.")
