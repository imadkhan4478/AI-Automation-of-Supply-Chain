"""
Dashboard — executive-first overview.

This is the landing page and the centerpiece of the C-level demo. It answers,
in five seconds: how healthy is the supply chain, what's changing, and what
needs attention. Detail lives one click deeper on the module pages.
"""

import streamlit as st

from backend import data_access as db
from components import ui, charts


def render():
    ui.page_header("Executive Dashboard", "Supply chain performance at a glance", module="dashboard")
    ui.chat_popover(db.ask_assistant)

    # --- Health banner: the one-line answer ---
    h = db.health()
    ui.health_banner(h["level"], h["message"])
    st.write("")

    # --- KPI grid (2 rows x 3) with trend + direction ---
    k = db.dashboard_kpis_rich()
    # Real weekly series behind 4 of the 6 cards, for a real (not fabricated)
    # sparkline. items_at_risk/open_imports are point-in-time snapshots with
    # no history table, so they intentionally get no sparkline.
    wk = db.weekly_trend()

    r1 = st.columns(3)
    with r1[0]:
        pv = k["purchase_value"]
        ui.kpi_card("Purchase Value", ui.money(pv["value"]), pv["delta"], pv["direction"], pv["good_when"],
                     spark=wk["purchase_value"].tolist())
    with r1[1]:
        ct = k["avg_cycle_time"]
        ui.kpi_card("Avg Cycle Time", ct["value"], ct["delta"], ct["direction"], ct["good_when"],
                     spark=wk["avg_cycle_days"].tolist())
    with r1[2]:
        do = k["delayed_orders"]
        ui.kpi_card("Delayed Orders", f"{do['value']:,}", do["delta"], do["direction"], do["good_when"],
                     spark=wk["delayed"].tolist())

    st.write("")
    r2 = st.columns(3)
    with r2[0]:
        ot = k["on_time_rate"]
        ui.kpi_card("On-Time Delivery", ot["value"], ot["delta"], ot["direction"], ot["good_when"],
                     spark=wk["on_time_pct"].tolist())
    with r2[1]:
        ir = k["items_at_risk"]
        ui.kpi_card("Items at Risk", f"{ir['value']}", ir["delta"], ir["direction"], ir["good_when"])
    with r2[2]:
        oi = k["open_imports"]
        ui.kpi_card("Open Imports", f"{oi['value']}", oi["delta"], oi["direction"], oi["good_when"])

    st.write("")
    st.write("")

    # --- Row: trend (wide) + attention panel (narrow) ---
    left, right = st.columns([2, 1])
    with left:
        ui.section("Purchase Value Trend")
        charts.trend_line(db.purchase_trend(), x="month", y="purchase_value_m")
        st.caption(ui.excluded_month_note(db.purchases_asof(), "PKR millions per month"))
    with right:
        ui.section("Attention Required")
        for a in db.alerts():
            ui.alert_row(a["level"], a["message"])

    st.write("")

    # --- Row: supplier performance + status composition + aging ---
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.section("Supplier On-Time %")
        charts.ranked_bar(db.supplier_performance(), "supplier", "on_time_pct",
                          height=300, benchmark=85, invert_color=False)
    with c2:
        ui.section("Purchase Status")
        labels, values = db.status_split("purchases")
        charts.donut(labels, values, height=300)
    with c3:
        ui.section("Delayed Orders — Days Overdue")
        charts.aging_buckets(db.aging(), "bucket", "orders", height=300)
