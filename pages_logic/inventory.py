"""Inventory — dashboard-first: KPIs + charts driven by the filter, with
the full stock table demoted to a "View real data" expander (with search).

The stock-health donut used to come from db.status_split("inventory"),
which was never connected to real data (a leftover stub) -- it's computed
here from the already-loaded, already-filtered DataFrame instead, which
both fixes that and makes it live to whatever filter is picked.
"""

import streamlit as st

from backend import data_access as db
from components import ui, charts


def render():
    ui.page_header("Inventory", "Current stock levels and reorder risk across branches", module="inventory")
    ui.chat_popover(db.ask_assistant)

    status = st.selectbox("Show items", ["All", "Below reorder", "OK"])
    data = db.stock(status=status)
    st.write("")

    # -------------------------------------------------- KPIs
    r1 = st.columns(3)
    with r1[0]:
        total_qty = int(data["available_qty"].sum()) if len(data) else 0
        ui.kpi_card("Available Units", f"{total_qty:,}")
    with r1[1]:
        total_stock = int(data["stock_qty"].sum()) if len(data) else 0
        ui.kpi_card("Total Stock Qty", f"{total_stock:,}")
    with r1[2]:
        ui.kpi_card("Items Shown", f"{len(data):,}")

    st.write("")
    r2 = st.columns(3)
    with r2[0]:
        below = int((data["stock_status"] == "Below reorder").sum()) if len(data) else 0
        ui.kpi_card("Below Reorder", f"{below}", direction="up" if below else None,
                    good_when="down", delta="need restocking" if below else "")
    with r2[1]:
        below_pct = (data["stock_status"] == "Below reorder").mean() * 100 if len(data) else 0
        ui.kpi_card("% Below Reorder", f"{below_pct:.0f}%" if len(data) else "—",
                    direction="up" if below_pct > 0 else None, good_when="down")
    with r2[2]:
        branches = data["branch"].nunique() if len(data) else 0
        ui.kpi_card("Branches Covered", f"{branches}")

    st.write("")
    st.write("")

    # -------------------------------------------------- Charts (all from the filtered data)
    if len(data):
        c1, c2, c3 = st.columns(3)
        with c1:
            ui.section("Stock Health")
            counts = data["stock_status"].value_counts()
            charts.donut(list(counts.index), list(counts.values), height=300)
        with c2:
            ui.section("Available Qty by Branch")
            by_branch = data.groupby("branch", as_index=False)["available_qty"].sum().sort_values(
                "available_qty", ascending=False)
            charts.category_bar(by_branch, "branch", "available_qty", height=300)
        with c3:
            ui.section("Top Items (stock qty)")
            by_item = (data.groupby("item", as_index=False)["stock_qty"].sum()
                       .sort_values("stock_qty", ascending=False).head(8))
            charts.ranked_bar(by_item, "item", "stock_qty", height=300)
    else:
        st.info("No items match the current filter.")

    st.write("")

    # -------------------------------------------------- More insight: reorder risk + lowest stock
    if len(data):
        d1, d2 = st.columns(2)
        with d1:
            ui.section("Reorder Risk by Branch")
            risk_by_branch = (
                data.assign(below=(data["stock_status"] == "Below reorder").astype(int))
                .groupby("branch", as_index=False)["below"].mean()
            )
            risk_by_branch["below"] *= 100
            risk_by_branch = risk_by_branch.sort_values("below", ascending=False)
            charts.ranked_bar(risk_by_branch, "branch", "below", height=280)
        with d2:
            ui.section("Lowest Stock Items")
            lowest = data.nsmallest(8, "available_qty")[["item", "available_qty"]]
            charts.ranked_bar(lowest, "item", "available_qty", height=280)

    st.write("")

    # -------------------------------------------------- Real data, on demand
    with st.expander("🔍 View real data / search"):
        search = st.text_input(
            "Search", placeholder="Search by item, item code, or branch.",
            label_visibility="collapsed",
        )
        table_data = data
        if search:
            needle = search.lower()
            mask = data.apply(
                lambda r: needle in str(r["item"]).lower() or needle in str(r["item_code"]).lower()
                or needle in str(r["branch"]).lower(),
                axis=1,
            )
            table_data = data[mask]
        ui.styled_table(table_data, status_col="stock_status", height=380)
