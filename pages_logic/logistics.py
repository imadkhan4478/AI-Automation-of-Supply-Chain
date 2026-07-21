"""Logistics — export and import shipment movements.

Export view  -> public.exports
Import view  -> public.shipment_details

Both come back from db.logistics() with a derived `status` column, so the
KPIs/charts colour-code the same way for either view. Dashboard-first, like
Purchases/Inventory/Imports: KPIs + charts driven by the kind + status data
already loaded, full table demoted to a "View real data" expander (search).
Columns shown are the REAL columns from the database (adapted to the data,
not the other way around) -- Export and Import have genuinely different
schemas, so the KPI/chart choices differ per kind, not just the labels.
"""

import pandas as pd
import streamlit as st

from backend import data_access as db
from components import ui, charts


def render():
    ui.page_header("Logistics", "Export and import shipments, ports, and movements", module="logistics")
    ui.chat_popover(db.ask_assistant)

    kind = st.selectbox("View", ["Export", "Import"])
    data = db.logistics(kind=kind)
    st.write("")

    if kind == "Export":
        _render_export(data)
    else:
        _render_import(data)

    st.write("")

    # -------------------------------------------------- Real data, on demand
    with st.expander("🔍 View real data / search"):
        cols = ["exp_no", "customer", "shipping_agent"] if kind == "Export" else ["bl_no", "pol", "pod"]
        search = st.text_input(
            "Search", placeholder=f"Search by {', '.join(cols)}.", label_visibility="collapsed",
        )
        table_data = data
        if search:
            needle = search.lower()
            mask = data.apply(lambda r: any(needle in str(r[c]).lower() for c in cols), axis=1)
            table_data = data[mask]
        ui.styled_table(table_data, status_col="status", height=380)


def _render_export(data):
    r1 = st.columns(3)
    with r1[0]:
        ui.kpi_card("Shipments Shown", f"{len(data):,}")
    with r1[1]:
        sailed = int(data["sailing_date"].notna().sum()) if len(data) else 0
        ui.kpi_card("Sailed", f"{sailed:,}")
    with r1[2]:
        handed = int((data["status"] == "Completed").sum()) if len(data) else 0
        ui.kpi_card("Handed Over", f"{handed:,}", direction="up" if handed else None, good_when="up")

    st.write("")
    r2 = st.columns(3)
    with r2[0]:
        pending = int((data["status"] == "Pending").sum()) if len(data) else 0
        ui.kpi_card("Pending", f"{pending:,}", direction="up" if pending else None, good_when="down")
    with r2[1]:
        customers = data["customer"].nunique() if len(data) else 0
        ui.kpi_card("Customers", f"{customers}")
    with r2[2]:
        agents = data["shipping_agent"].nunique() if len(data) else 0
        ui.kpi_card("Shipping Agents", f"{agents}")

    st.write("")
    st.write("")

    if len(data):
        c1, c2, c3 = st.columns(3)
        with c1:
            ui.section("Status")
            counts = data["status"].value_counts()
            charts.donut(list(counts.index), list(counts.values), height=300)
        with c2:
            ui.section("By Shipping Agent")
            grp = (data.assign(shipping_agent=data["shipping_agent"].fillna("Unknown"))
                   .groupby("shipping_agent").size().reset_index(name="shipments")
                   .sort_values("shipments", ascending=False).head(8))
            charts.ranked_bar(grp, "shipping_agent", "shipments", height=300)
        with c3:
            ui.section("By Customer")
            grp2 = (data.assign(customer=data["customer"].fillna("Unknown"))
                    .groupby("customer").size().reset_index(name="shipments")
                    .sort_values("shipments", ascending=False).head(8))
            charts.category_bar(grp2, "customer", "shipments", height=300)

        st.write("")
        d1, d2 = st.columns(2)
        with d1:
            ui.section("Shipments Over Time")
            trend_src = data.dropna(subset=["sailing_date"])
            if len(trend_src):
                by_month = (trend_src.assign(month=pd.to_datetime(trend_src["sailing_date"]).dt.to_period("M").dt.to_timestamp())
                            .groupby("month", as_index=False).size().rename(columns={"size": "shipments"}))
                charts.trend_line(by_month, "month", "shipments", height=280)
                note = ui.partial_period_note(pd.to_datetime(trend_src["sailing_date"]).max())
                if note:
                    st.caption(note)
            else:
                st.caption("No sailing dates in the current view yet.")
        with d2:
            ui.section("By Payment Term")
            pt_src = data.dropna(subset=["payment_term"])
            if len(pt_src):
                grp3 = (pt_src.groupby("payment_term").size().reset_index(name="shipments")
                         .sort_values("shipments", ascending=False))
                charts.category_bar(grp3, "payment_term", "shipments", height=280)
            else:
                st.caption("No payment term data in the current view.")
    else:
        st.info("No shipments match the current filter.")


def _render_import(data):
    r1 = st.columns(3)
    with r1[0]:
        ui.kpi_card("Shipments Shown", f"{len(data):,}")
    with r1[1]:
        cleared = int((data["status"] == "Cleared").sum()) if len(data) else 0
        ui.kpi_card("Cleared", f"{cleared:,}", direction="up" if cleared else None, good_when="up")
    with r1[2]:
        in_transit = int((data["status"] == "In Transit").sum()) if len(data) else 0
        ui.kpi_card("In Transit", f"{in_transit:,}")

    st.write("")
    r2 = st.columns(3)
    with r2[0]:
        pending = int((data["status"] == "Pending Clearance").sum()) if len(data) else 0
        ui.kpi_card("Pending Clearance", f"{pending:,}", direction="up" if pending else None, good_when="down")
    with r2[1]:
        total_value = data["total_value_pkr_batch_wise"].sum() if len(data) else 0
        ui.kpi_card("Total Value", ui.money(total_value))
    with r2[2]:
        ports = data["pod"].nunique() if len(data) else 0
        ui.kpi_card("Destination Ports", f"{ports}")

    st.write("")
    st.write("")

    if len(data):
        c1, c2, c3 = st.columns(3)
        with c1:
            ui.section("Status")
            counts = data["status"].value_counts()
            charts.donut(list(counts.index), list(counts.values), height=300)
        with c2:
            ui.section("By Destination Port")
            grp = (data.assign(pod=data["pod"].fillna("Unknown"))
                   .groupby("pod").size().reset_index(name="shipments")
                   .sort_values("shipments", ascending=False).head(8))
            charts.ranked_bar(grp, "pod", "shipments", height=300)
        with c3:
            ui.section("By Mode of Shipment")
            grp2 = (data.assign(mode_of_shipment=data["mode_of_shipment"].fillna("Unknown"))
                    .groupby("mode_of_shipment").size().reset_index(name="shipments")
                    .sort_values("shipments", ascending=False))
            charts.category_bar(grp2, "mode_of_shipment", "shipments", height=300)

        st.write("")
        d1, d2 = st.columns(2)
        with d1:
            ui.section("Shipments Over Time")
            trend_src = data.dropna(subset=["etd"])
            if len(trend_src):
                by_month = (trend_src.assign(month=pd.to_datetime(trend_src["etd"]).dt.to_period("M").dt.to_timestamp())
                            .groupby("month", as_index=False).size().rename(columns={"size": "shipments"}))
                charts.trend_line(by_month, "month", "shipments", height=280)
                note = ui.partial_period_note(pd.to_datetime(trend_src["etd"]).max())
                if note:
                    st.caption(note)
            else:
                st.caption("No ETD dates in the current view yet.")
        with d2:
            ui.section("By Clearance Mode")
            cm_src = data.dropna(subset=["clearance_mode"])
            if len(cm_src):
                grp3 = (cm_src.groupby("clearance_mode").size().reset_index(name="shipments")
                         .sort_values("shipments", ascending=False))
                charts.category_bar(grp3, "clearance_mode", "shipments", height=280)
            else:
                st.caption("No clearance mode data in the current view.")
    else:
        st.info("No shipments match the current filter.")
