"""Reports — custom report builder.

Workflow: choose a source, pick any columns to include, add value filters on
any column, optionally compare a measure across a dimension or across time,
preview, then export (CSV / real Excel / real PDF) or turn into a dashboard.
The dashboard/save-report buttons are wired to intents the backend will
fulfil later; everything else (including both export formats) is fully
real today -- no stubbed downloads.
"""

import datetime
import io

import streamlit as st
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend import data_access as db
from components import ui, charts


# Map each source to its loader, its natural status column (for row coloring),
# and its primary date column (for the quick date-range filter).
#
# Logistics (2026-07-21): the page itself is export-only now -- it maps to
# the business's own export pipeline stages (shipments/packing/transport/
# documentation), each its own real table, not an Export/Import toggle.
# Import shipment tracking belongs to the "Imports" source above
# (import_details) instead. Mirrors the Logistics page's four views exactly
# so the report builder can never see anything the page itself can't.
SOURCES = {
    "Purchases":               {"loader": lambda: db.purchases(), "status_col": "status", "date_col": "purchase_date"},
    "Inventory":               {"loader": lambda: db.stock(),     "status_col": "stock_status", "date_col": None},
    "Imports":                 {"loader": lambda: db.imports(),   "status_col": "current_status", "date_col": "demand_date"},
    "Logistics — Shipments":    {"loader": lambda: db.logistics_shipments(), "status_col": "status", "date_col": "port_in_date"},
    "Logistics — Packing":      {"loader": lambda: db.logistics_packing(), "status_col": "status", "date_col": "actual_rfd_date"},
    "Logistics — Transport":    {"loader": lambda: db.logistics_shifting(), "status_col": "status", "date_col": "execution_date"},
    "Logistics — Documentation": {"loader": lambda: db.logistics_documentation(), "status_col": "status", "date_col": None},
}

_AGG_FUNCS = {"Sum": "sum", "Average": "mean", "Count": "count"}


def _is_date_series(series):
    sample = series.dropna()
    if sample.empty:
        return False
    return isinstance(sample.iloc[0], (datetime.date, datetime.datetime, pd.Timestamp))


def _fmt_number(value):
    if value is None or pd.isna(value):
        return "—"
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:,.1f}M"
    if abs(value) >= 1_000:
        return f"{value/1_000:,.1f}K"
    return f"{value:,.1f}" if value != int(value) else f"{int(value):,}"


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
    active_filter_summary = []

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
                picked = st.multiselect(f"Status ({status_col})", options, default=[],
                                         key=f"quick_status_{source}")
                if picked:
                    filtered = filtered[filtered[status_col].astype(str).isin(picked)]
                    quick_filter_count += 1
                    active_filter_summary.append(f"{status_col} in {{{', '.join(picked)}}}")
        with qcols[1]:
            if date_col and date_col in all_cols and _is_date_series(full[date_col]):
                non_null = full[date_col].dropna()
                if not non_null.empty:
                    lo, hi = min(non_null), max(non_null)
                    if lo == hi:
                        st.caption(f"**{date_col}**: all = {lo}")
                    else:
                        sel = st.slider(f"Date range ({date_col})", lo, hi, (lo, hi),
                                         key=f"quick_date_{source}")
                        filtered = filtered[filtered[date_col].apply(
                            lambda v: pd.notna(v) and sel[0] <= v <= sel[1])]
                        if sel != (lo, hi):
                            quick_filter_count += 1
                            active_filter_summary.append(f"{date_col} between {sel[0]} and {sel[1]}")
        st.write("")

    # -------------------------------------------------- 3. Columns
    ui.section("3 · Select columns to include")
    col_key = f"columns_{source}"
    sa1, sa2, sa3 = st.columns([1, 1, 6])
    with sa1:
        if st.button("Select all", key=f"select_all_{source}", width="stretch"):
            st.session_state[col_key] = all_cols
    with sa2:
        if st.button("Clear", key=f"clear_cols_{source}", width="stretch"):
            st.session_state[col_key] = []
    chosen_cols = st.multiselect(
        "Columns", all_cols, default=[], label_visibility="collapsed",
        help="Pick any combination of columns for your report — nothing is "
             "pre-selected, so the report starts from a blank slate.",
        key=col_key,
    )
    if not chosen_cols:
        st.info("Select at least one column to build your report (or click \"Select all\" above).")
        return

    # -------------------------------------------------- 4. Advanced filters (any column)
    with st.expander("4 · Advanced filters — any column"):
        st.caption("Filter on any column. Text/category columns offer value pickers; "
                   "numeric and date columns offer a range.")
        filter_cols = st.multiselect(
            "Filter which columns?", all_cols, default=[],
            help="Choose one or more columns to filter on.",
            key=f"filter_cols_{source}",
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
                            sel = st.slider(col, lo, hi, (lo, hi), key=f"adv_{source}_{col}")
                            filtered = filtered[filtered[col].between(sel[0], sel[1])]
                            active_filter_summary.append(f"{col} between {sel[0]:g} and {sel[1]:g}")
                    elif _is_date_series(series):
                        non_null = series.dropna()
                        lo, hi = min(non_null), max(non_null)
                        if lo == hi:
                            st.caption(f"**{col}**: all = {lo}")
                        else:
                            sel = st.slider(col, lo, hi, (lo, hi), key=f"adv_{source}_{col}")
                            filtered = filtered[filtered[col].apply(
                                lambda v: pd.notna(v) and sel[0] <= v <= sel[1])]
                            active_filter_summary.append(f"{col} between {sel[0]} and {sel[1]}")
                    else:
                        options = sorted(series.dropna().astype(str).unique().tolist())
                        picked = st.multiselect(col, options, default=[], key=f"adv_{source}_{col}")
                        if picked:
                            filtered = filtered[filtered[col].astype(str).isin(picked)]
                            active_filter_summary.append(f"{col} in {{{', '.join(picked)}}}")

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

    # -------------------------------------------------- 5. Compare (optional)
    ui.section("5 · Compare (optional)")
    numeric_cols = [c for c in chosen_cols if pd.api.types.is_numeric_dtype(result[c])]
    date_like_cols = [c for c in chosen_cols if _is_date_series(result[c])]
    categorical_cols = [c for c in chosen_cols if c not in numeric_cols and c not in date_like_cols]

    comparison_table = None  # exported to Excel/PDF if a comparison is built
    comparison_caption = ""

    if not numeric_cols:
        st.caption("Include at least one numeric column to build a comparison.")
    else:
        by_options = ["None"] + categorical_cols
        if date_like_cols:
            by_options.append("Time period (month over month)")
        cc1, cc2, cc3 = st.columns([2, 2, 1])
        with cc1:
            compare_by = st.selectbox("Compare by", by_options, key=f"compare_by_{source}")
        with cc2:
            measure = st.selectbox("Measure", numeric_cols, key=f"compare_measure_{source}")
        with cc3:
            agg_label = st.selectbox("Aggregate", list(_AGG_FUNCS.keys()), key=f"compare_agg_{source}")
        agg_fn = _AGG_FUNCS[agg_label]

        if compare_by == "Time period (month over month)":
            date_pick = date_like_cols[0]
            if len(date_like_cols) > 1:
                date_pick = st.selectbox("Date column", date_like_cols, key=f"compare_datecol_{source}")
            d = result.dropna(subset=[date_pick]).copy()
            if len(d):
                d["_month"] = pd.to_datetime(d[date_pick]).dt.to_period("M")
                months = sorted(d["_month"].unique())
                if len(months) >= 2:
                    cur_m, prev_m = months[-1], months[-2]
                    cur_series = d.loc[d["_month"] == cur_m, measure]
                    prev_series = d.loc[d["_month"] == prev_m, measure]
                    cur_val = getattr(cur_series, agg_fn)()
                    prev_val = getattr(prev_series, agg_fn)()
                    delta_pct = ((cur_val - prev_val) / prev_val * 100) if prev_val else None
                    pc1, pc2 = st.columns(2)
                    with pc1:
                        ui.kpi_card(f"{agg_label} of {measure} — {cur_m}", _fmt_number(cur_val))
                    with pc2:
                        ui.kpi_card(
                            f"{agg_label} of {measure} — {prev_m}", _fmt_number(prev_val),
                            delta=f"{abs(delta_pct):.0f}% vs prior period" if delta_pct is not None else "",
                            direction=("up" if delta_pct >= 0 else "down") if delta_pct is not None else None,
                            good_when="up",
                        )
                    comparison_table = pd.DataFrame({
                        "period": [str(prev_m), str(cur_m)],
                        f"{agg_label.lower()}_{measure}": [prev_val, cur_val],
                    })
                    comparison_caption = f"{agg_label} of {measure}, {prev_m} vs {cur_m}"
                else:
                    st.caption("Not enough distinct months in the filtered data to compare periods.")
            else:
                st.caption(f"No rows with a {date_pick} value in the filtered data.")
        elif compare_by != "None":
            grouped = (result.dropna(subset=[compare_by])
                       .groupby(compare_by, as_index=False)[measure].agg(agg_fn)
                       .sort_values(measure, ascending=False))
            if len(grouped):
                ui.section(f"{agg_label} of {measure} by {compare_by}")
                charts.ranked_bar(grouped.head(12), compare_by, measure, height=320)
                if len(grouped) > 12:
                    st.caption(f"Showing top 12 of {len(grouped)} {compare_by} values.")
                comparison_table = grouped
                comparison_caption = f"{agg_label} of {measure} by {compare_by}"
            else:
                st.caption("No data to compare for the current filters.")

    # -------------------------------------------------- 6. Preview
    st.write("")
    ui.section("6 · Preview")
    sc = status_col if status_col in result.columns else None
    ui.styled_table(result, status_col=sc, height=340)

    # -------------------------------------------------- 7. Actions
    ui.section("7 · Do something with this report")
    a1, a2, a3, a4, a5 = st.columns(5)
    slug = source.lower().replace(" — ", "_").replace(" ", "_")

    with a1:
        st.download_button(
            "⬇  Export CSV",
            result.to_csv(index=False).encode("utf-8"),
            file_name=f"{slug}_report.csv",
            mime="text/csv", width="stretch",
        )
    with a2:
        st.download_button(
            "⬇  Export Excel",
            _to_excel_bytes(result, comparison_table),
            file_name=f"{slug}_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    with a3:
        st.download_button(
            "⬇  Export PDF",
            _to_pdf_bytes(result, source, active_filter_summary, comparison_table, comparison_caption),
            file_name=f"{slug}_report.pdf",
            mime="application/pdf", width="stretch",
        )
    with a4:
        if st.button("📊  Create Dashboard", width="stretch",
                     help="Turn this report into a live dashboard tile."):
            _remember_definition(source, chosen_cols, filter_cols, mode="dashboard")
            st.success("Dashboard request captured — the backend will build a live "
                       "dashboard from this report definition.")
    with a5:
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


# ======================================================================
#  EXPORTS — real .xlsx (openpyxl) and real .pdf (reportlab), not stubs
# ======================================================================
def _to_excel_bytes(df, comparison_table=None):
    """Real .xlsx, built in-memory. A "Comparison" sheet is added only when
    the user actually built one on-screen -- otherwise just the data.
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Report")
        if comparison_table is not None and len(comparison_table):
            comparison_table.to_excel(writer, index=False, sheet_name="Comparison")
    return buf.getvalue()


def _to_pdf_bytes(df, source, filter_summary, comparison_table, comparison_caption, max_rows=300):
    """Real PDF, built in-memory with reportlab -- no external binary
    dependency (unlike wkhtmltopdf-based approaches), so it works the same
    on any machine this app runs on.

    Row count is capped at max_rows so a large export doesn't produce a
    thousand-page PDF; CSV/Excel remain the way to get the full dataset.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24,
    )
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(f"Qadri Group — {source} Report", styles["Title"]),
        Paragraph(f"Generated {datetime.datetime.now():%Y-%m-%d %H:%M}", styles["Normal"]),
    ]
    if filter_summary:
        elements.append(Paragraph("Filters: " + "; ".join(filter_summary), styles["Normal"]))
    elements.append(Spacer(1, 12))

    if comparison_table is not None and len(comparison_table):
        elements.append(Paragraph(comparison_caption, styles["Heading3"]))
        elements.append(_build_table(comparison_table, header_color="#8B5CF6"))
        elements.append(Spacer(1, 16))

    elements.append(Paragraph("Report Data", styles["Heading3"]))
    shown = df.head(max_rows)
    elements.append(_build_table(shown))
    if len(df) > max_rows:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(
            f"Showing first {max_rows:,} of {len(df):,} rows. Export CSV or Excel for the full dataset.",
            styles["Italic"],
        ))

    doc.build(elements)
    return buf.getvalue()


def _build_table(df, header_color="#4F46E5"):
    n_cols = max(len(df.columns), 1)
    font_size = 8 if n_cols <= 8 else (6.5 if n_cols <= 14 else 5.5)
    data = [list(df.columns)] + df.astype(str).values.tolist()
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F8FB")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E6E8EF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table
