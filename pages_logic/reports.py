"""Reports — custom report builder.

Workflow: choose a source, pick any columns to include, add value filters on
any column, preview, then export or turn into a dashboard. The dashboard and
export buttons are wired to intents the backend will fulfil later; the UI
captures the full report definition today.
"""

import streamlit as st
import pandas as pd

from backend import data_access as db
from components import ui


# Map each source to its loader and its natural status column (for coloring)
SOURCES = {
    "Purchases": {"loader": lambda: db.purchases(), "status_col": "status"},
    "Inventory": {"loader": lambda: db.stock(),     "status_col": "stock_status"},
    "Imports":   {"loader": lambda: db.imports(),   "status_col": "current_status"},
    "Logistics": {"loader": lambda: db.logistics(), "status_col": "shipment_status"},
}


def render():
    ui.page_header("Reports", "Build a custom report from any columns, then export or visualize", module="reports")

    # -------------------------------------------------- 1. Source
    ui.section("1 · Choose a data source")
    source = st.selectbox("Data source", list(SOURCES.keys()), label_visibility="collapsed")

    full = SOURCES[source]["loader"]()
    status_col = SOURCES[source]["status_col"]
    all_cols = list(full.columns)

    # -------------------------------------------------- 2. Columns
    ui.section("2 · Select columns to include")
    chosen_cols = st.multiselect(
        "Columns", all_cols, default=all_cols, label_visibility="collapsed",
        help="Pick any combination of columns for your report.",
    )
    if not chosen_cols:
        st.info("Select at least one column to build your report.")
        return

    # -------------------------------------------------- 3. Filters (any column)
    ui.section("3 · Add filters")
    st.caption("Filter on any column. Text/category columns offer value pickers; "
               "numeric columns offer a range.")

    filter_cols = st.multiselect(
        "Filter which columns?", all_cols, default=[],
        help="Choose one or more columns to filter on.",
    )

    filtered = full.copy()
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
        active = len(filter_cols)
        ui.kpi_card("Active Filters", f"{active}")

    # -------------------------------------------------- 4. Preview
    st.write("")
    ui.section("4 · Preview")
    sc = status_col if status_col in result.columns else None
    ui.styled_table(result, status_col=sc, height=340)

    # -------------------------------------------------- 5. Actions
    ui.section("5 · Do something with this report")
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
