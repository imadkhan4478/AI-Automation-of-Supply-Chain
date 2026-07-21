"""Inventory — dashboard-first: KPIs + charts driven by the filter, with
the full stock table demoted to a "View real data" expander (with search).

The stock-health donut used to come from db.status_split("inventory"),
which was never connected to real data (a leftover stub) -- it's computed
here from the already-loaded, already-filtered DataFrame instead, which
both fixes that and makes it live to whatever filter is picked.

'Below reorder' → 'Out of Stock' rename (2026-07-21): the old placeholder
rule was available_qty <= 0, which IS what "out of stock" means -- it was
just mislabeled. A real 'Below Reorder' tier (business's actual formula:
(issuance_3m/90)*safety_days for safety stock, +(issuance_3m/90)*lead_time
for reorder level) needs safety_days/lead_time_days, which aren't in the
database yet -- see db.stock()'s docstring. Once those exist this page
adds that tier back; it isn't guessed at here.

Chart choice note: any chart that SUMS available_qty will read as flat/
zero the moment you filter to "Out of Stock" (available_qty <= 0 for every
row, by definition) -- not a bug, just a chart picking the wrong measure
for that filter. "Items by Branch" below counts rows instead of summing
qty, so it stays meaningful under every filter, including this one.
"""

import streamlit as st

from backend import data_access as db
from components import ui, charts


def render():
    ui.page_header("Inventory", "Current stock levels and usage-based reorder risk", module="inventory")
    ui.chat_popover(db.ask_assistant)

    status = st.selectbox("Show items", ["All", "Out of Stock", "OK"])
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
        oos = int((data["stock_status"] == "Out of Stock").sum()) if len(data) else 0
        ui.kpi_card("Out of Stock", f"{oos}", direction="up" if oos else None,
                    good_when="down", delta="need restocking" if oos else "")
    with r2[1]:
        oos_pct = (data["stock_status"] == "Out of Stock").mean() * 100 if len(data) else 0
        ui.kpi_card("% Out of Stock", f"{oos_pct:.0f}%" if len(data) else "—",
                    direction="up" if oos_pct > 0 else None, good_when="down")
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
            ui.section("Items by Branch")
            by_branch = data.groupby("branch").size().reset_index(name="items").sort_values(
                "items", ascending=False)
            charts.category_bar(by_branch, "branch", "items", height=300)
        with c3:
            ui.section("Top Items (stock qty)")
            by_item = (data.groupby("item", as_index=False)["stock_qty"].sum()
                       .sort_values("stock_qty", ascending=False).head(8))
            charts.ranked_bar(by_item, "item", "stock_qty", height=300)
    else:
        st.info("No items match the current filter.")

    st.write("")

    # -------------------------------------------------- More insight: out-of-stock rate + runway
    if len(data):
        d1, d2 = st.columns(2)
        with d1:
            ui.section("Out-of-Stock Rate by Branch")
            risk_by_branch = (
                data.assign(oos=(data["stock_status"] == "Out of Stock").astype(int))
                .groupby("branch", as_index=False)["oos"].mean()
            )
            risk_by_branch["oos"] *= 100
            risk_by_branch = risk_by_branch.sort_values("oos", ascending=False)
            charts.ranked_bar(risk_by_branch, "branch", "oos", height=280)
        with d2:
            ui.section("Lowest Days of Stock Remaining")
            runway = data.dropna(subset=["days_of_stock"])
            if len(runway):
                lowest = runway.nsmallest(8, "days_of_stock")[["item", "days_of_stock"]]
                charts.ranked_bar(lowest, "item", "days_of_stock", height=280)
            else:
                st.caption("No items in the current view have recent issuance history to estimate a runway from.")

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
