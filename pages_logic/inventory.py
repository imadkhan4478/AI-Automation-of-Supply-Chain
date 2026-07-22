"""Inventory — dashboard-first: KPIs + charts driven by the filter, with
the full stock table demoted to a "View real data" expander (with search).

The stock-health donut used to come from db.status_split("inventory"),
which was never connected to real data (a leftover stub) -- it's computed
here from the already-loaded, already-filtered DataFrame instead, which
both fixes that and makes it live to whatever filter is picked.

Three real status tiers (2026-07-21, once ab_items -- safety_days/
lead_time_days per item+branch, provided by the business -- landed in the
database): 'Out of Stock' (available_qty <= 0), 'Below Reorder'
(available_qty < the business's real reorder-level formula), 'OK'. See
db.stock()'s docstring for the formula and coverage caveats.

Chart choice note: any chart that SUMS available_qty reads as flat/zero
the moment you filter to a tier defined by low available_qty -- not a
chart bug, just the wrong measure for that filter. "Items by Branch"
below counts rows instead of summing qty, so it stays meaningful under
every filter.

Category filter + search (2026-07-21): db.stock() now also joins in
item_category/uom/specs/group_name/material_standard from `items`, so a
search hit surfaces everything on file for that item, not just its name/
branch/qty. Category and Branch (4 real branches) are their own filters
alongside status. hold_qty is now pulled in too (was never selected
before) and shown as its own KPI -- reserved stock, not available for use,
distinct from available_qty/stock_qty.

Search, surfaced (2026-07-21): the search box used to live inside the
collapsed "View real data" expander, where it only filtered the table --
easy to miss, and left the KPIs/charts above showing the unsearched set.
It's now its own always-visible row right under the filters, and it
filters `data` itself before anything downstream (KPIs, charts, table)
is computed -- so searching "steel" narrows the whole page, not just the
table at the bottom.
"""

import streamlit as st

from backend import data_access as db
from components import ui, charts

_RISK_TIERS = ["Out of Stock", "Below Reorder"]


def render():
    ui.page_header("Inventory", "Current stock levels and usage-based reorder risk", module="inventory")
    ui.chat_popover(db.ask_assistant)

    f1, f2, f3 = st.columns(3)
    with f1:
        status = ui.multiselect_filter("Show items", ["All", "Out of Stock", "Below Reorder", "OK"])
    with f2:
        category = ui.multiselect_filter("Category", db.inventory_category_list())
    with f3:
        branch = ui.multiselect_filter("Branch", db.inventory_branch_list())
    data = db.stock(status=status, category=category, branch=branch)

    search = st.text_input(
        "Search",
        placeholder="🔍 Search by item, item code, branch, category, or specs...",
        label_visibility="collapsed",
    )
    if search:
        needle = search.lower()
        mask = data.apply(
            lambda r: needle in str(r["item"]).lower() or needle in str(r["item_code"]).lower()
            or needle in str(r["branch"]).lower() or needle in str(r["item_category"]).lower()
            or needle in str(r["specs"]).lower(),
            axis=1,
        )
        data = data[mask].reset_index(drop=True)
    st.write("")

    # -------------------------------------------------- KPIs
    r1 = st.columns(4)
    with r1[0]:
        total_qty = int(data["available_qty"].sum()) if len(data) else 0
        ui.kpi_card("Available Units", f"{total_qty:,}")
    with r1[1]:
        total_stock = int(data["stock_qty"].sum()) if len(data) else 0
        ui.kpi_card("Total Stock Qty", f"{total_stock:,}")
    with r1[2]:
        total_hold = int(data["hold_qty"].sum()) if len(data) else 0
        ui.kpi_card("On Hold", f"{total_hold:,}", sub="reserved, not available")
    with r1[3]:
        ui.kpi_card("Items Shown", f"{len(data):,}")

    st.write("")
    r2 = st.columns(3)
    with r2[0]:
        oos = int((data["stock_status"] == "Out of Stock").sum()) if len(data) else 0
        ui.kpi_card("Out of Stock", f"{oos}", direction="up" if oos else None,
                    good_when="down", delta="need restocking" if oos else "")
    with r2[1]:
        below = int((data["stock_status"] == "Below Reorder").sum()) if len(data) else 0
        ui.kpi_card("Below Reorder", f"{below}", direction="up" if below else None,
                    good_when="down", delta="approaching reorder point" if below else "")
    with r2[2]:
        at_risk_pct = data["stock_status"].isin(_RISK_TIERS).mean() * 100 if len(data) else 0
        ui.kpi_card("% At Risk", f"{at_risk_pct:.0f}%" if len(data) else "—",
                    direction="up" if at_risk_pct > 0 else None, good_when="down",
                    sub="out of stock + below reorder")

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

    # -------------------------------------------------- More insight: at-risk rate + runway
    if len(data):
        d1, d2 = st.columns(2)
        with d1:
            ui.section("At-Risk Rate by Branch")
            risk_by_branch = (
                data.assign(at_risk=data["stock_status"].isin(_RISK_TIERS).astype(int))
                .groupby("branch", as_index=False)["at_risk"].mean()
            )
            risk_by_branch["at_risk"] *= 100
            risk_by_branch = risk_by_branch.sort_values("at_risk", ascending=False)
            charts.ranked_bar(risk_by_branch, "branch", "at_risk", height=280)
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
    with st.expander("🔍 View real data"):
        ui.styled_table(data, status_col="stock_status", height=380)
