"""Imports — dashboard-first: KPIs + charts driven by the filter, with the
full shipment table demoted to a "View real data" expander (with search).

The clearance-status donut used to call db.status_split("imports")
unfiltered -- so picking a status in the dropdown would filter the table
but leave the donut showing the full unfiltered breakdown, which read as
inconsistent. It's computed here from the already-filtered DataFrame
instead, so the two always agree.
"""

import pandas as pd
import streamlit as st

from backend import data_access as db
from components import ui, charts


def render():
    ui.page_header("Imports", "Import shipments, values, and customs clearance", module="imports")
    ui.chat_popover(db.ask_assistant)

    status = st.selectbox("Show imports", db.imports_status_list())
    data = db.imports(status=status)
    st.write("")

    # -------------------------------------------------- KPIs
    r1 = st.columns(3)
    with r1[0]:
        total_value = data["total_value_pkr"].sum() if len(data) else 0
        ui.kpi_card("Total Value", ui.money(total_value))
    with r1[1]:
        total_wt = data["total_wt_ton"].sum() if len(data) else 0
        ui.kpi_card("Total Weight", f"{total_wt:,.0f} t")
    with r1[2]:
        ui.kpi_card("Shipments Shown", f"{len(data):,}")

    st.write("")
    r2 = st.columns(3)
    with r2[0]:
        open_n = int((~data["current_status"].isin(["Arrived at Works", "Order Cancelled"])).sum()) if len(data) else 0
        ui.kpi_card("Open", f"{open_n}", sub="not yet arrived/cancelled")
    with r2[1]:
        clearance = int((data["current_status"] == "Under Custom Clearance").sum()) if len(data) else 0
        ui.kpi_card("Under Clearance", f"{clearance}", direction="up" if clearance else None,
                    good_when="down", delta="awaiting customs" if clearance else "")
    with r2[2]:
        suppliers = data["supplier"].nunique() if len(data) else 0
        ui.kpi_card("Suppliers", f"{suppliers}")

    st.write("")
    st.write("")

    # -------------------------------------------------- Charts (all from the filtered data)
    if len(data):
        c1, c2, c3 = st.columns(3)
        with c1:
            ui.section("Clearance Status")
            counts = data["current_status"].value_counts()
            charts.donut(list(counts.index), list(counts.values), height=300)
        with c2:
            ui.section("Value by Country")
            by_country = (data.groupby("supplier_country", as_index=False)["total_value_pkr"].sum()
                          .sort_values("total_value_pkr", ascending=False).head(8))
            charts.ranked_bar(by_country, "supplier_country", "total_value_pkr", height=300)
        with c3:
            ui.section("Value by Category")
            by_cat = data.groupby("category", as_index=False)["total_value_pkr"].sum().sort_values(
                "total_value_pkr", ascending=False)
            charts.category_bar(by_cat, "category", "total_value_pkr", height=300)
    else:
        st.info("No imports match the current filter.")

    st.write("")

    # -------------------------------------------------- More insight: trend + docs status
    if len(data):
        trend_src = data.dropna(subset=["demand_date"])
        d1, d2 = st.columns(2)
        with d1:
            ui.section("Import Value Trend (by month)")
            if len(trend_src):
                by_month = (trend_src.assign(month=pd.to_datetime(trend_src["demand_date"]).dt.to_period("M").dt.to_timestamp())
                            .groupby("month", as_index=False)["total_value_pkr"].sum())
                charts.trend_line(by_month, "month", "total_value_pkr", height=280)
                note = ui.partial_period_note(pd.to_datetime(trend_src["demand_date"]).max())
                if note:
                    st.caption(note)
            else:
                st.caption("No demand dates in the current view yet.")
        with d2:
            ui.section("Top Suppliers (value)")
            sup_src = data.dropna(subset=["supplier"])
            if len(sup_src):
                by_supplier = (sup_src.groupby("supplier", as_index=False)["total_value_pkr"].sum()
                               .sort_values("total_value_pkr", ascending=False).head(8))
                charts.ranked_bar(by_supplier, "supplier", "total_value_pkr", height=280)
            else:
                st.caption("No supplier data in the current view.")

    st.write("")

    # -------------------------------------------------- Real data, on demand
    with st.expander("🔍 View real data / search"):
        search = st.text_input(
            "Search", placeholder="Search by import ref, customer, or supplier.",
            label_visibility="collapsed",
        )
        table_data = data
        if search:
            needle = search.lower()
            mask = data.apply(
                lambda r: needle in str(r["import_ref"]).lower() or needle in str(r["customer"]).lower()
                or needle in str(r["supplier"]).lower(),
                axis=1,
            )
            table_data = data[mask]
        ui.styled_table(table_data, status_col="current_status", height=380)
