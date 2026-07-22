"""Logistics — export shipments and documentation, plus packing and inland
transport (shifting), which cover local jobs too, not just export ones.
(2026-07-21) No longer an Export/Import toggle -- import SHIPMENT tracking
already has its own tab (Imports, import_details); Logistics maps to the
business's own pipeline stages instead, each backed by its own real table
(export_shipments / packing_details / shifting_movements / export_documents).

Dashboard-first like every other tab: KPIs + charts driven by the status
filter, full table demoted to a "View real data" expander (search). See
backend.data_access's logistics_* functions for which pre-built metric
views checked out as real vs. had to be left out as broken.
"""

import pandas as pd
import streamlit as st

from backend import data_access as db
from components import ui, charts


def render():
    ui.page_header(
        "Logistics", "Export shipments/documentation, plus packing and transport",
        module="logistics",
    )
    ui.chat_popover(db.ask_assistant)

    # "Export ___" only on Shipments and Documentation -- those two really
    # are export-specific (export_shipments, export_documents both key off
    # export_id). Packing and Transport are NOT export-scoped: packing_
    # details and shifting_movements cover local jobs/moves too (only
    # ~9% of packing_details rows even have an export_id) -- calling them
    # "Export Packing"/"Export Transport" would misstate what's in them.
    view = st.selectbox(
        "View", ["Export Shipments", "Packing", "Transport", "Export Documentation"],
    )
    st.write("")

    if view == "Export Shipments":
        _render_shipments()
    elif view == "Packing":
        _render_packing()
    elif view == "Transport":
        _render_transport()
    else:
        _render_documentation()


# ======================================================================
#  SHIPMENTS  (export_shipments + v_shipment_metrics)
# ======================================================================
def _render_shipments():
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        status = ui.multiselect_filter("Status", db.logistics_shipment_status_list(), key="log_ship_status")
    with f2:
        stage = ui.multiselect_filter("Shipment Stage", db.logistics_shipment_stage_list(), key="log_ship_stage")
    with f3:
        shipping_line = ui.multiselect_filter("Shipping Line", db.logistics_shipping_line_list(), key="log_ship_line")
    with f4:
        country = ui.multiselect_filter("Country", db.logistics_shipment_country_list(), key="log_ship_country")
    data = db.logistics_shipments(status=status, stage=stage, shipping_line=shipping_line, country=country)
    st.write("")

    r1 = st.columns(3)
    with r1[0]:
        ui.kpi_card("Shipments Shown", f"{len(data):,}")
    with r1[1]:
        delivered = int((data["status"] == "Delivered").sum()) if len(data) else 0
        ui.kpi_card("Delivered", f"{delivered:,}", direction="up" if delivered else None, good_when="up")
    with r1[2]:
        unlinked = int(data["export_id"].isna().sum()) if len(data) else 0
        ui.kpi_card("Not Yet Linked to an Export", f"{unlinked}", sub="tracked ahead of the export record")

    st.write("")
    r2 = st.columns(3)
    with r2[0]:
        total_cost = data["total_logistics_cost"].sum() if len(data) else 0
        ui.kpi_card("Total Logistics Cost", ui.money(total_cost))
    with r2[1]:
        cost_per_kg = data.loc[data["cost_per_kg"] > 0, "cost_per_kg"].mean() if len(data) else None
        ui.kpi_card("Avg Cost / kg", f"PKR {cost_per_kg:,.1f}" if pd.notna(cost_per_kg) else "—")
    with r2[2]:
        countries = data["country"].nunique() if len(data) else 0
        ui.kpi_card("Countries", f"{countries}")

    st.write("")
    st.write("")

    if len(data):
        c1, c2, c3 = st.columns(3)
        with c1:
            ui.section("Status")
            counts = data["status"].value_counts()
            charts.donut(list(counts.index), list(counts.values), height=300)
        with c2:
            ui.section("By Country")
            grp = (data.dropna(subset=["country"]).groupby("country").size()
                   .reset_index(name="shipments").sort_values("shipments", ascending=False).head(8))
            charts.ranked_bar(grp, "country", "shipments", height=300)
        with c3:
            ui.section("By Port of Discharge")
            grp2 = (data.dropna(subset=["pod"]).groupby("pod").size()
                    .reset_index(name="shipments").sort_values("shipments", ascending=False).head(8))
            charts.category_bar(grp2, "pod", "shipments", height=300)

        st.write("")
        d1, d2 = st.columns(2)
        with d1:
            ui.section("Shipments Over Time (by week)")
            trend_src = data.dropna(subset=["port_in_date"])
            if len(trend_src):
                by_week = ui.weekly_trend_points(trend_src.assign(_n=1), "port_in_date", "_n").rename(columns={"_n": "shipments"})
                charts.trend_line(by_week, "week", "shipments", height=280)
                note = ui.partial_week_note(pd.to_datetime(trend_src["port_in_date"]).max())
                if note:
                    st.caption(note)
            else:
                st.caption("No port-in dates in the current view yet.")
        with d2:
            ui.section("Avg Cost / kg by Country")
            cost_src = data.dropna(subset=["country"])
            cost_src = cost_src[cost_src["cost_per_kg"] > 0]
            if len(cost_src):
                grp3 = (cost_src.groupby("country", as_index=False)["cost_per_kg"].mean()
                        .sort_values("cost_per_kg", ascending=False).head(8))
                charts.ranked_bar(grp3, "country", "cost_per_kg", height=280)
            else:
                st.caption("No cost/kg data in the current view.")
    else:
        st.info("No shipments match the current filter.")

    st.write("")
    with st.expander("🔍 View real data / search"):
        search = st.text_input(
            "Search", placeholder="Search by export no, customer, or country.",
            label_visibility="collapsed", key="log_ship_search",
        )
        table_data = data
        if search:
            needle = search.lower()
            mask = data.apply(
                lambda r: needle in str(r["exp_no"]).lower() or needle in str(r["customer"]).lower()
                or needle in str(r["country"]).lower(),
                axis=1,
            )
            table_data = data[mask]
        ui.styled_table(table_data, status_col="status", height=380)


# ======================================================================
#  PACKING  (packing_details)
# ======================================================================
def _render_packing():
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        status = ui.multiselect_filter("Status", db.logistics_packing_status_list(), key="log_pack_status")
    with f2:
        works = ui.multiselect_filter("Works", db.logistics_packing_works_list(), key="log_pack_works")
    with f3:
        product_category = ui.multiselect_filter("Product Category", db.logistics_packing_category_list(), key="log_pack_cat")
    with f4:
        business_type = ui.multiselect_filter("Business Type", db.logistics_packing_business_type_list(), key="log_pack_biztype")
    data = db.logistics_packing(status=status, works=works, product_category=product_category, business_type=business_type)
    st.write("")

    r1 = st.columns(3)
    with r1[0]:
        ui.kpi_card("Packing Jobs Shown", f"{len(data):,}")
    with r1[1]:
        pending = int((data["status"] == "Pending Packing").sum()) if len(data) else 0
        ui.kpi_card("Pending Packing", f"{pending:,}", direction="up" if pending else None, good_when="down")
    with r1[2]:
        in_progress = int((data["status"] == "In Progress").sum()) if len(data) else 0
        ui.kpi_card("In Progress", f"{in_progress:,}")

    st.write("")
    r2 = st.columns(3)
    with r2[0]:
        avg_delay = data["rfd_delay_days"].dropna().mean() if len(data) else None
        ui.kpi_card("Avg RFD Delay", f"{avg_delay:.1f} days" if pd.notna(avg_delay) else "—",
                    direction="up" if pd.notna(avg_delay) and avg_delay > 0 else None, good_when="down")
    with r2[1]:
        total_cost = data["actual_packing_cost"].sum() if len(data) else 0
        ui.kpi_card("Total Packing Cost", ui.money(total_cost))
    with r2[2]:
        cats = data["product_category"].nunique() if len(data) else 0
        ui.kpi_card("Product Categories", f"{cats}")

    st.write("")
    st.write("")

    if len(data):
        c1, c2, c3 = st.columns(3)
        with c1:
            ui.section("Status")
            counts = data["status"].value_counts()
            charts.donut(list(counts.index), list(counts.values), height=300)
        with c2:
            ui.section("By Product Category")
            grp = (data.dropna(subset=["product_category"]).groupby("product_category").size()
                   .reset_index(name="jobs").sort_values("jobs", ascending=False).head(8))
            charts.ranked_bar(grp, "product_category", "jobs", height=300)
        with c3:
            ui.section("By Business Type")
            grp2 = (data.dropna(subset=["business_type"]).groupby("business_type").size()
                    .reset_index(name="jobs").sort_values("jobs", ascending=False))
            charts.category_bar(grp2, "business_type", "jobs", height=300)

        st.write("")
        d1, d2 = st.columns(2)
        with d1:
            ui.section("RFD Delay")
            delay_src = data.dropna(subset=["rfd_delay_days"])
            if len(delay_src):
                buckets = pd.cut(
                    delay_src["rfd_delay_days"], [-10_000, 0, 7, 30, 10_000],
                    labels=["On time", "1-7 days late", "8-30 days late", "30+ days late"],
                )
                by_bucket = buckets.value_counts().reindex(
                    ["On time", "1-7 days late", "8-30 days late", "30+ days late"]).reset_index()
                by_bucket.columns = ["bucket", "jobs"]
                charts.category_bar(by_bucket, "bucket", "jobs", height=280)
            else:
                st.caption("No jobs in the current view have both a target and actual RFD date.")
        with d2:
            ui.section("By Customer (job count)")
            cust = (data.dropna(subset=["customer"]).groupby("customer").size()
                    .reset_index(name="jobs").sort_values("jobs", ascending=False).head(8))
            if len(cust):
                charts.ranked_bar(cust, "customer", "jobs", height=280)
            else:
                st.caption("No customer data in the current view.")
    else:
        st.info("No packing jobs match the current filter.")

    st.write("")
    with st.expander("🔍 View real data / search"):
        search = st.text_input(
            "Search", placeholder="Search by customer, jobs no, or product category.",
            label_visibility="collapsed", key="log_pack_search",
        )
        table_data = data
        if search:
            needle = search.lower()
            mask = data.apply(
                lambda r: needle in str(r["customer"]).lower() or needle in str(r["jobs_no"]).lower()
                or needle in str(r["product_category"]).lower(),
                axis=1,
            )
            table_data = data[mask]
        ui.styled_table(table_data, status_col="status", height=380)


# ======================================================================
#  TRANSPORT / SHIFTING  (shifting_movements + v_shifting_metrics)
# ======================================================================
def _render_transport():
    f1, f2, f3 = st.columns(3)
    with f1:
        status = ui.multiselect_filter("Status", db.logistics_shifting_status_list(), key="log_shift_status")
    with f2:
        movement_type = ui.multiselect_filter("Movement Type", db.logistics_movement_type_list(), key="log_shift_movetype")
    with f3:
        payment_status = ui.multiselect_filter("Payment Status", db.logistics_payment_status_list(), key="log_shift_paystatus")
    data = db.logistics_shifting(status=status, movement_type=movement_type, payment_status=payment_status)
    st.write("")

    r1 = st.columns(3)
    with r1[0]:
        ui.kpi_card("Movements Shown", f"{len(data):,}")
    with r1[1]:
        delivered = int((data["status"] == "Delivered").sum()) if len(data) else 0
        ui.kpi_card("Delivered", f"{delivered:,}", direction="up" if delivered else None, good_when="up")
    with r1[2]:
        in_progress = int((data["status"] == "In Progress").sum()) if len(data) else 0
        ui.kpi_card("In Progress", f"{in_progress:,}")

    st.write("")
    r2 = st.columns(3)
    with r2[0]:
        total_freight = data["actual_freight_rs"].sum() if len(data) else 0
        ui.kpi_card("Total Freight Cost", ui.money(total_freight))
    with r2[1]:
        total_savings = data["savings_rs"].dropna().sum() if len(data) else 0
        ui.kpi_card("Total Savings", ui.money(total_savings) if total_savings else "—")
    with r2[2]:
        transporters = data["transporter"].nunique() if len(data) else 0
        ui.kpi_card("Transporters", f"{transporters}")

    st.write("")
    st.write("")

    if len(data):
        c1, c2, c3 = st.columns(3)
        with c1:
            ui.section("Status")
            counts = data["status"].value_counts()
            charts.donut(list(counts.index), list(counts.values), height=300)
        with c2:
            ui.section("By Transporter")
            grp = (data.dropna(subset=["transporter"]).groupby("transporter").size()
                   .reset_index(name="movements").sort_values("movements", ascending=False).head(8))
            charts.ranked_bar(grp, "transporter", "movements", height=300)
        with c3:
            ui.section("By Destination Province")
            grp2 = (data.dropna(subset=["province"]).groupby("province").size()
                    .reset_index(name="movements").sort_values("movements", ascending=False))
            charts.category_bar(grp2, "province", "movements", height=300)

        st.write("")
        d1, d2 = st.columns(2)
        with d1:
            ui.section("Movements Over Time (by week)")
            trend_src = data.dropna(subset=["execution_date"])
            if len(trend_src):
                by_week = ui.weekly_trend_points(trend_src.assign(_n=1), "execution_date", "_n").rename(columns={"_n": "movements"})
                charts.trend_line(by_week, "week", "movements", height=280)
                note = ui.partial_week_note(pd.to_datetime(trend_src["execution_date"]).max())
                if note:
                    st.caption(note)
            else:
                st.caption("No execution dates in the current view yet.")
        with d2:
            ui.section("Freight Cost by Transporter")
            freight_src = data.dropna(subset=["transporter"])
            if len(freight_src):
                grp3 = (freight_src.groupby("transporter", as_index=False)["actual_freight_rs"].sum()
                        .sort_values("actual_freight_rs", ascending=False).head(8))
                charts.ranked_bar(grp3, "transporter", "actual_freight_rs", height=280)
            else:
                st.caption("No transporter data in the current view.")
    else:
        st.info("No movements match the current filter.")

    st.write("")
    with st.expander("🔍 View real data / search"):
        search = st.text_input(
            "Search", placeholder="Search by customer, transporter, or destination.",
            label_visibility="collapsed", key="log_shift_search",
        )
        table_data = data
        if search:
            needle = search.lower()
            mask = data.apply(
                lambda r: needle in str(r["customer"]).lower() or needle in str(r["transporter"]).lower()
                or needle in str(r["destination"]).lower(),
                axis=1,
            )
            table_data = data[mask]
        ui.styled_table(table_data, status_col="status", height=380)


# ======================================================================
#  DOCUMENTATION  (v_documentation_completion + export_documents)
# ======================================================================
def _render_documentation():
    status = ui.multiselect_filter("Status", db.logistics_documentation_status_list(), key="log_doc_status")
    data = db.logistics_documentation(status=status)
    st.write("")

    r1 = st.columns(3)
    with r1[0]:
        ui.kpi_card("Exports Tracked", f"{len(data):,}")
    with r1[1]:
        complete = int((data["status"] == "Complete").sum()) if len(data) else 0
        ui.kpi_card("Complete", f"{complete:,}", direction="up" if complete else None, good_when="up")
    with r1[2]:
        incomplete = int((data["status"] == "Incomplete").sum()) if len(data) else 0
        ui.kpi_card("Incomplete", f"{incomplete:,}", direction="up" if incomplete else None, good_when="down")

    st.write("")
    r2 = st.columns(3)
    with r2[0]:
        avg_pct = data["completion_pct"].mean() if len(data) else None
        ui.kpi_card("Avg Completion", f"{avg_pct:.0f}%" if pd.notna(avg_pct) else "—")
    with r2[1]:
        avg_customs = data["customs_completion_pct"].mean() if len(data) else None
        ui.kpi_card("Avg Customs Completion", f"{avg_customs:.0f}%" if pd.notna(avg_customs) else "—")
    with r2[2]:
        pending_docs = int(data["pending_documents"].sum()) if len(data) else 0
        ui.kpi_card("Pending Documents", f"{pending_docs:,}")

    st.write("")
    st.write("")

    if len(data):
        c1, c2, c3 = st.columns(3)
        with c1:
            ui.section("Status")
            counts = data["status"].value_counts()
            charts.donut(list(counts.index), list(counts.values), height=300)
        with c2:
            ui.section("Lowest Completion % (exports)")
            lowest = data.nsmallest(8, "completion_pct")[["exp_no", "completion_pct"]].dropna()
            if len(lowest):
                charts.ranked_bar(lowest, "exp_no", "completion_pct", height=300)
            else:
                st.caption("No completion data in the current view.")
        with c3:
            ui.section("Completion by Category")
            by_cat = pd.DataFrame({
                "category": ["Customs", "Customer", "Bank"],
                "avg_pct": [
                    data["customs_completion_pct"].mean(),
                    data["customer_completion_pct"].mean(),
                    data["bank_completion_pct"].mean(),
                ],
            }).dropna()
            if len(by_cat):
                charts.category_bar(by_cat, "category", "avg_pct", height=300)
            else:
                st.caption("No category completion data in the current view.")
    else:
        st.info("No exports match the current filter.")

    st.write("")
    ui.section("Document Types (all exports)")
    st.caption("Not scoped to the status filter above -- documents are tracked per export, "
               "not per completion tier, so this covers every export.")
    doc_types = db.logistics_document_types()
    if len(doc_types):
        dt1, dt2 = st.columns(2)
        with dt1:
            by_type = (doc_types.groupby("document_type", as_index=False)["n"].sum()
                       .sort_values("n", ascending=False).head(10))
            charts.category_bar(by_type, "document_type", "n", height=280)
        with dt2:
            by_status = doc_types.groupby("status", as_index=False)["n"].sum().sort_values("n", ascending=False)
            charts.donut(list(by_status["status"]), list(by_status["n"]), height=280)

    st.write("")
    with st.expander("🔍 View real data / search"):
        search = st.text_input(
            "Search", placeholder="Search by export no or batch no.",
            label_visibility="collapsed", key="log_doc_search",
        )
        table_data = data
        if search:
            needle = search.lower()
            mask = data.apply(
                lambda r: needle in str(r["exp_no"]).lower() or needle in str(r["batch_no"]).lower(),
                axis=1,
            )
            table_data = data[mask]
        ui.styled_table(table_data, status_col="status", height=380)
