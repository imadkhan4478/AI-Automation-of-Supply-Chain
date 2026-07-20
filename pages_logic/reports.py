"""Reports — custom report builder.

Workflow: choose a source, pick any columns to include, add value filters on
any column, preview, then export or turn into a dashboard. The dashboard and
export buttons are wired to intents the backend will fulfil later; the UI
captures the full report definition today.
"""

import datetime

import streamlit as st
import pandas as pd

from backend import data_access as db
from components import ui


# Map each source to its loader, its natural status column (for row coloring),
# and its primary date column (for the quick date-range filter). "Logistics"'s
# status_col was "shipment_status" here but the connected logistics() function
# names the real column "status" (a leftover from the old stub, which used a
# different name) -- fixed, since it silently broke row coloring on that report.
SOURCES = {
    "Purchases": {"loader": lambda: db.purchases(), "status_col": "status", "date_col": "purchase_date"},
    "Inventory": {"loader": lambda: db.stock(),     "status_col": "stock_status", "date_col": None},
    "Imports":   {"loader": lambda: db.imports(),   "status_col": "current_status", "date_col": "demand_date"},
    "Logistics": {"loader": lambda: db.logistics(), "status_col": "status", "date_col": "sailing_date"},
}


def _is_date_series(series):
    sample = series.dropna()
    if sample.empty:
        return False
    return isinstance(sample.iloc[0], (datetime.date, datetime.datetime, pd.Timestamp))


def render():
    ui.page_header("Reports", "Build a custom report from any columns, then export or visualize", module="reports")
    ui.chat_popover(db.ask_assistant)

    # -------------------------------------------------- 1. Source
    ui.section("1 · Choose a data source")
    source = st.selectbox("Data source", list(SOURCES.keys()), label_visibility="collapsed")

    full = SOURCES[source]["loader"]()
    status_col = SOURCES[source]["status_col"]
    date_col = SOURCES[source]["date_col"]
    all_cols = list(full.columns)
    filtered = full.copy()
    quick_filter_count = 0

    # -------------------------------------------------- 2. Quick filters
    # The most common filtering need (status, date range) shown immediately —
    # no extra "which columns do you want to filter" step first. Advanced
    # per-column filtering (step 4) still covers everything else.
    if status_col in all_cols or date_col:
        ui.section("2 · Quick filters")
        qcols = st.columns(2)
        with qcols[0]:
            if status_col in all_cols:
                options = sorted(full[status_col].dropna().astype(str).unique().tolist())
                picked = st.multiselect(f"Status ({status_col})", options, default=[])
                if picked:
                    filtered = filtered[filtered[status_col].astype(str).isin(picked)]
                    quick_filter_count += 1
        with qcols[1]:
            if date_col and date_col in all_cols and _is_date_series(full[date_col]):
                non_null = full[date_col].dropna()
                if not non_null.empty:
                    lo, hi = min(non_null), max(non_null)
                    if lo == hi:
                        st.caption(f"**{date_col}**: all = {lo}")
                    else:
                        sel = st.slider(f"Date range ({date_col})", lo, hi, (lo, hi))
                        filtered = filtered[filtered[date_col].apply(
                            lambda v: pd.notna(v) and sel[0] <= v <= sel[1])]
                        if sel != (lo, hi):
                            quick_filter_count += 1
        st.write("")

    # -------------------------------------------------- 3. Columns
    ui.section("3 · Select columns to include")
    chosen_cols = st.multiselect(
        "Columns", all_cols, default=all_cols, label_visibility="collapsed",
        help="Pick any combination of columns for your report.",
    )
    if not chosen_cols:
        st.info("Select at least one column to build your report.")
        return

    # -------------------------------------------------- 4. Advanced filters (any column)
    with st.expander("4 · Advanced filters — any column"):
        st.caption("Filter on any column. Text/category columns offer value pickers; "
                   "numeric and date columns offer a range.")
        filter_cols = st.multiselect(
            "Filter which columns?", all_cols, default=[],
            help="Choose one or more columns to filter on.",
        )
        if filter_cols:
            fcols = st.columns(min(len(filter_cols), 3))
            for i, col in enumerate(filter_cols):
                with fcols[i % len(fcols)]:
                    series = full[col]
                    if pd.api.types.is_numeric_dtype(series):
                        lo, hi = float(series.min()), float(series.max())
                        if lo == hi:
                            st.caption(f"**{col}**: all = {lo:g}")
                        else:
                            sel = st.slider(col, lo, hi, (lo, hi))
                            filtered = filtered[filtered[col].between(sel[0], sel[1])]
                    elif _is_date_series(series):
                        non_null = series.dropna()
                        lo, hi = min(non_null), max(non_null)
                        if lo == hi:
                            st.caption(f"**{col}**: all = {lo}")
                        else:
                            sel = st.slider(col, lo, hi, (lo, hi), key=f"adv_{col}")
                            filtered = filtered[filtered[col].apply(
                                lambda v: pd.notna(v) and sel[0] <= v <= sel[1])]
                    else:
                        options = sorted(series.dropna().astype(str).unique().tolist())
                        picked = st.multiselect(col, options, default=[])
                        if picked:
                            filtered = filtered[filtered[col].astype(str).isin(picked)]

    # Apply chosen columns to the final result
    result = filtered[chosen_cols]

    # -------------------------------------------------- Summary KPIs
    st.write("")
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.kpi_card("Rows in Report", f"{len(result):,}")
    with c2:
        ui.kpi_card("Columns", f"{result.shape[1]}")
    with c3:
        active = quick_filter_count + len(filter_cols)
        ui.kpi_card("Active Filters", f"{active}")

    # -------------------------------------------------- 5. Preview
    st.write("")
    ui.section("5 · Preview")
    sc = status_col if status_col in result.columns else None
    ui.styled_table(result, status_col=sc, height=340)

    # -------------------------------------------------- 6. Actions
    ui.section("6 · Do something with this report")
    a1, a2, a3, a4 = st.columns(4)

    with a1:
        st.download_button(
            "⬇  Export CSV",
            result.to_csv(index=False).encode("utf-8"),
            file_name=f"{source.lower()}_report.csv",
            mime="text/csv", width="stretch",
        )
    with a2:
        st.download_button(
            "⬇  Export Excel",
            result.to_csv(index=False).encode("utf-8"),  # backend will supply real .xlsx
            file_name=f"{source.lower()}_report.csv",
            mime="text/csv", width="stretch",
        )
    with a3:
        if st.button("📊  Create Dashboard", width="stretch",
                     help="Turn this report into a live dashboard tile."):
            _remember_definition(source, chosen_cols, filter_cols, mode="dashboard")
            st.success("Dashboard request captured — the backend will build a live "
                       "dashboard from this report definition.")
    with a4:
        if st.button("💾  Save Report", width="stretch",
                     help="Save this report definition to reuse later."):
            _remember_definition(source, chosen_cols, filter_cols, mode="saved")
            st.success("Report definition saved.")


def _remember_definition(source, columns, filters, mode):
    """Capture the report definition in session state.

    This is the exact object the backend will consume to (a) re-run the report
    or (b) build a dashboard tile. Storing it here means the UI is already
    'done' — only the backend action remains.
    """
    definition = {
        "source": source,
        "columns": columns,
        "filter_columns": filters,
        "mode": mode,
    }
    st.session_state.setdefault("report_definitions", []).append(definition)
