"""Purchases — dashboard-first: KPIs + charts driven by the filters, with
the full data table demoted to a "View real data" expander (with search)
rather than being the primary view. Everything below the filters is
recomputed from the same filtered DataFrame, so it's live to whatever
status/supplier is picked -- no separate query path to keep in sync.
"""

import streamlit as st

from backend import data_access as db
from components import ui, charts


def render():
    ui.page_header("Purchases", "Track purchase orders, suppliers, and delivery status", module="purchases")
    ui.chat_popover(db.ask_assistant)

    f1, f2 = st.columns(2)
    with f1:
        status = st.selectbox("Show orders", ["All", "Pending", "Completed", "Delayed"])
    with f2:
        supplier = st.selectbox("Supplier", db.supplier_list())

    data = db.purchases(status=status, supplier=supplier)
    st.write("")

    # -------------------------------------------------- KPIs
    r1 = st.columns(3)
    with r1[0]:
        total_value = data["amount"].sum() if len(data) else 0
        ui.kpi_card("Total Value", ui.money(total_value))
    with r1[1]:
        ui.kpi_card("Orders", f"{len(data):,}")
    with r1[2]:
        avg_value = data["amount"].mean() if len(data) else 0
        ui.kpi_card("Avg Order Value", ui.money(avg_value) if len(data) else "—")

    st.write("")
    r2 = st.columns(3)
    with r2[0]:
        delayed = int((data["status"] == "Delayed").sum()) if len(data) else 0
        ui.kpi_card("Delayed", f"{delayed}", direction="up" if delayed else None, good_when="down",
                    delta="in current view" if delayed else "")
    with r2[1]:
        on_time_pct = (data["status"] != "Delayed").mean() * 100 if len(data) else 0
        ui.kpi_card("On-Time Rate", f"{on_time_pct:.0f}%" if len(data) else "—")
    with r2[2]:
        top_supplier = data.groupby("supplier")["amount"].sum().idxmax() if len(data) else "—"
        ui.kpi_card("Top Supplier (value)", top_supplier, sub="in current view")

    st.write("")
    st.write("")

    # -------------------------------------------------- Charts (all from the filtered data)
    if len(data):
        c1, c2, c3 = st.columns(3)
        with c1:
            ui.section("Value by Branch")
            by_branch = data.groupby("branch", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
            charts.category_bar(by_branch, "branch", "amount", height=300)
        with c2:
            ui.section("Status Breakdown")
            counts = data["status"].value_counts()
            charts.donut(list(counts.index), list(counts.values), height=300)
        with c3:
            ui.section("Top Suppliers (value)")
            by_supplier = (data.groupby("supplier", as_index=False)["amount"].sum()
                           .sort_values("amount", ascending=False).head(8))
            charts.ranked_bar(by_supplier, "supplier", "amount", height=300)
    else:
        st.info("No orders match the current filter.")

    st.write("")

    # -------------------------------------------------- Real data, on demand
    with st.expander("🔍 View real data / search"):
        search = st.text_input(
            "Search", placeholder="Search by item, supplier, PO number, or ref no.",
            label_visibility="collapsed",
        )
        table_data = data
        if search:
            needle = search.lower()
            mask = data.apply(
                lambda r: needle in str(r["item"]).lower() or needle in str(r["po_number"]).lower()
                or needle in str(r["ref_no"]).lower() or needle in str(r["supplier"]).lower(),
                axis=1,
            )
            table_data = data[mask]
        ui.styled_table(table_data, status_col="status", height=380)
