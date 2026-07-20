"""
Backend interface layer.

This is the ONLY module the frontend pages are allowed to import for data.
Pages never touch the database, the stubs, or any calculation directly —
they call functions here.

Right now every function forwards to stubs/fake_data.py. When the real
backend is ready, we change ONLY the bodies of these functions to call
the real database/analytics modules. The function names and their return
shapes stay identical, so no page code changes.

    Page  ->  backend.data_access  ->  (today) stubs
                                        (later) real database / analytics
"""

from stubs import fake_data as _src

import pandas as pd
from sqlalchemy import text
from backend.db_connection import get_engine


# --- Dashboard -------------------------------------------------------
def dashboard_kpis():
    return _src.get_dashboard_kpis()


def purchase_trend():
    """Real monthly purchase value (PKR millions) from purchases_data.

    NOTE: the current extract only spans ~2 months (see purchases.purchase
    min/max), so this may show as few as 2 points until more history
    accumulates in the database. That's the real data, not a bug.
    """
    query = text("""
        SELECT
            TO_CHAR(DATE_TRUNC('month', purchase), 'Mon YYYY') AS month,
            SUM(amount) / 1e6 AS purchase_value_m
        FROM public.purchases_data
        WHERE purchase IS NOT NULL
        GROUP BY DATE_TRUNC('month', purchase)
        ORDER BY DATE_TRUNC('month', purchase)
    """)
    return pd.read_sql(query, get_engine())


def weekly_trend():
    """Real weekly buckets from purchases_data — feeds the KPI sparklines.

    NOTE: the current extract spans ~1 month, so this is a handful of real
    points (however many ISO weeks exist in the data), not a fabricated
    smooth series. `ui.kpi_card`'s sparkline renders nothing if it gets
    fewer than 2 points, so a thin extract degrades gracefully.
    """
    query = text("""
        SELECT
            DATE_TRUNC('week', purchase) AS week,
            SUM(amount) AS purchase_value,
            SUM(CASE WHEN required_d IS NOT NULL AND purchase > required_d THEN 1 ELSE 0 END) AS delayed,
            COUNT(*) AS total,
            AVG(purchase - ppc_store) AS avg_cycle_days
        FROM public.purchases_data
        WHERE purchase IS NOT NULL
        GROUP BY week
        ORDER BY week
    """)
    df = pd.read_sql(query, get_engine())
    df["on_time_pct"] = (df["total"] - df["delayed"]) / df["total"] * 100
    return df


def alerts():
    """Real attention panel, derived from suppliers / stock / purchases / imports.

    NOTE: 'chronically late' (on-time < 70%) and 'stuck import' (past its
    required date, still open) are placeholder business rules, same spirit
    as the delay/reorder rules elsewhere in this module — swap the
    threshold once the business defines a real one.
    """
    engine = get_engine()
    out = []

    sup = supplier_performance()
    late = sup[sup["on_time_pct"] < 70].sort_values("on_time_pct")
    if len(late):
        names = ", ".join(late["supplier"].head(3))
        out.append({"level": "high", "message": f"{len(late)} supplier(s) chronically late (on-time < 70%): {names}"})

    stock_df = stock()
    n_risk = int((stock_df["stock_status"] == "Below reorder").sum())
    if n_risk:
        out.append({"level": "high", "message": f"{n_risk} items below reorder point"})

    this_month = pd.read_sql(text("""
        SELECT COUNT(*) AS n
        FROM public.purchases_data
        WHERE required_d IS NOT NULL AND purchase > required_d
          AND DATE_TRUNC('month', purchase) = (SELECT MAX(DATE_TRUNC('month', purchase)) FROM public.purchases_data)
    """), engine)
    n_delayed = int(this_month.iloc[0]["n"])
    if n_delayed:
        out.append({"level": "medium", "message": f"{n_delayed} purchase orders delayed this month"})

    stuck_imports = pd.read_sql(text("""
        SELECT COUNT(*) AS n FROM public.import_details
        WHERE current_status NOT IN ('Arrived at Works', 'Order Cancelled')
          AND req_date IS NOT NULL AND req_date < CURRENT_DATE
    """), engine)
    n_stuck = int(stuck_imports.iloc[0]["n"])
    if n_stuck:
        out.append({"level": "low", "message": f"{n_stuck} imports past their required date, still open"})

    return out


# --- Purchases -------------------------------------------------------
def purchases(status="All", supplier="All"):
    """Real data: purchase orders joined to item names, with a derived status.

    purchases_data has no status column, so it is derived from the dates:
      - no purchase date yet                      -> 'Pending'
      - purchased after the required date         -> 'Delayed'
      - otherwise                                 -> 'Completed'

    NOTE: this is a placeholder business rule (like the stock reorder rule).
    If the business defines delay differently (e.g. vs ppc_store date, or a
    grace period), only this CASE expression changes — the page stays as is.
    """
    query = text("""
        SELECT
            p.ref_no,
            p.po_number,
            p.supplier,
            COALESCE(i.item, p.item_code) AS item,
            p.branch,
            p.qty,
            p.amount,
            p.required_d AS required_date,
            p.purchase   AS purchase_date,
            p.mop,
            CASE
                WHEN p.purchase IS NULL THEN 'Pending'
                WHEN p.required_d IS NOT NULL
                     AND p.purchase > p.required_d THEN 'Delayed'
                ELSE 'Completed'
            END AS status
        FROM public.purchases_data p
        LEFT JOIN public.items i ON i.item_code = p.item_code
        ORDER BY p.purchase DESC NULLS FIRST, p.ref_no
    """)
    df = pd.read_sql(query, get_engine())

    if status != "All":
        df = df[df["status"] == status].reset_index(drop=True)
    if supplier != "All":
        df = df[df["supplier"] == supplier].reset_index(drop=True)
    return df


def supplier_list():
    """Real data: distinct suppliers that actually appear in purchases_data."""
    query = text("""
        SELECT DISTINCT supplier
        FROM public.purchases_data
        WHERE supplier IS NOT NULL AND supplier <> ''
        ORDER BY supplier
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["supplier"].tolist()


# --- Inventory -------------------------------------------------------
def stock(status="All"):
    """Real data: current stock joined to item names, with a computed status.

    The stock table has no item name (it's in `items`) and no stored status,
    so we join for the name and derive `stock_status` here. This keeps the
    return shape identical to what the Inventory page expects, so the page
    does not change.

    NOTE: 'Below reorder' is currently a placeholder rule (available_qty = 0)
    because the stock table has no reorder-level column yet. Replace with a
    real reorder threshold once the business provides one.
    """
    query = text("""
        SELECT
            s.item_code,
            COALESCE(i.item, s.item_code) AS item,
            s.branch,
            s.stock_qty,
            s.available_qty,
            CASE WHEN s.available_qty <= 0 THEN 'Below reorder'
                 ELSE 'OK' END AS stock_status
        FROM public.stock s
        LEFT JOIN public.items i ON i.item_code = s.item_code
        ORDER BY s.item_code
    """)
    df = pd.read_sql(query, get_engine())

    if status != "All":
        df = df[df["stock_status"] == status].reset_index(drop=True)
    return df


# --- Imports ---------------------------------------------------------
def imports(status="All"):
    """Real data: import shipments from import_details.

    `current_status` is the real workflow state (10 distinct business values
    such as 'Arrived at Works', 'In Transit', 'Under Custom Clearance').
    No join needed — customer/supplier/value all live on this table.

    NOTE: total_value_pkr is often 0 in the source (value is recorded in
    total_value_fc / foreign currency); both are returned so the page/team
    can decide which to display once an FX rule is provided.
    """
    query = text("""
        SELECT
            import_ref,
            branch,
            customer,
            supplier,
            supplier_country,
            category,
            total_wt_ton,
            total_value_fc,
            total_value_pkr,
            demand_date,
            req_date,
            gin_date,
            docs_status,
            current_status
        FROM public.import_details
        ORDER BY import_id
    """)
    df = pd.read_sql(query, get_engine())

    if status != "All":
        df = df[df["current_status"] == status].reset_index(drop=True)
    return df


def imports_status_list():
    """Real distinct current_status values, most common first."""
    query = text("""
        SELECT current_status
        FROM public.import_details
        WHERE current_status IS NOT NULL AND current_status <> ''
        GROUP BY current_status
        ORDER BY COUNT(*) DESC
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["current_status"].tolist()



# --- Logistics -------------------------------------------------------
def logistics(kind="Export"):
    """Real data: export shipments (public.exports) or import shipments
    (public.shipment_details), depending on `kind`.
 
    Both branches return a DataFrame with a derived `status` column so the
    Logistics page can colour-code rows the same way for either view.
 
    Status rules are PLACEHOLDERS (like stock's reorder rule) until the
    business confirms real definitions:
      - Export : 'Completed' when handed_over_to is filled, else 'Pending'.
      - Import : 'Cleared' when gate_out is set, else 'In Transit' when an
                 eta_final exists, else 'Pending Clearance'.
 
    Note: richer logistics metrics (transit days, cost/kg, packing on-time,
    documentation completion %) are available later from the pre-built views
    v_shipment_metrics / v_packing_metrics / v_shifting_metrics /
    v_documentation_completion — wire those in during customization.
    """
    engine = get_engine()
 
    if kind == "Import":
        query = text("""
            SELECT
                bl_no,
                pol,
                pod,
                mode_of_shipment,
                s_line,
                local_agent,
                total_value_pkr_batch_wise,
                etd,
                eta_final,
                transit_time,
                gate_out,
                clearance_mode
            FROM public.shipment_details
            ORDER BY eta_final DESC NULLS LAST
        """)
        df = pd.read_sql(query, engine)
 
        def _imp_status(row):
            if pd.notna(row["gate_out"]):
                return "Cleared"
            if pd.notna(row["eta_final"]):
                return "In Transit"
            return "Pending Clearance"
 
        df["status"] = df.apply(_imp_status, axis=1) if len(df) else []
        return df
 
    # Default: Export
    query = text("""
        SELECT
            exp_no,
            customer,
            shipping_agent,
            bl_type,
            payment_term,
            sailing_date,
            gate_out_date,
            handed_over_to
        FROM public.exports
        ORDER BY sailing_date DESC NULLS LAST
    """)
    df = pd.read_sql(query, engine)
    df["status"] = (
        df["handed_over_to"].apply(
            lambda v: "Completed" if pd.notna(v) and str(v).strip() != "" else "Pending"
        )
        if len(df) else []
    )
    return df

# --- Assistant -------------------------------------------------------
def ask_assistant(question):
    return _src.ask_assistant(question)


# --- Executive / enriched (added for enterprise dashboard) -----------
def dashboard_kpis_rich():
    """Real KPI cards for the executive dashboard: this calendar month vs last.

    NOTE: purchases_data has zero rows with `purchase IS NULL` in the
    current extract -- every order already has a completion date, so there
    is no real "open/pending order" population. The old "Pending Orders"
    card is relabeled to Avg Cycle Time (days from ppc_store to purchase),
    a metric the data can actually prove; the key changed from
    `pending_orders` to `avg_cycle_time` to match (see dashboard.py).

    `items_at_risk` (stock) and `open_imports` (import_details) are
    point-in-time snapshots -- there's no history table to diff against --
    so their deltas honestly say "current snapshot" instead of an invented
    month-over-month change.

    Comparing a full prior month to a partial current month (if the current
    month is still in progress) will show a real dip in raw totals; this is
    not corrected/prorated, since that would be inventing data.
    """
    engine = get_engine()

    scoped = pd.read_sql(text("""
        WITH scoped AS (
            SELECT
                amount,
                (purchase - ppc_store) AS cycle_days,
                CASE WHEN required_d IS NOT NULL AND purchase > required_d
                     THEN 'Delayed' ELSE 'Completed' END AS status,
                DATE_TRUNC('month', purchase) AS month
            FROM public.purchases_data
            WHERE purchase IS NOT NULL
        ),
        recent_months AS (
            SELECT DISTINCT month FROM scoped ORDER BY month DESC LIMIT 2
        )
        SELECT
            month,
            COUNT(*) AS total,
            SUM(amount) AS purchase_value,
            SUM(CASE WHEN status = 'Delayed' THEN 1 ELSE 0 END) AS delayed,
            AVG(cycle_days) AS avg_cycle_days
        FROM scoped
        WHERE month IN (SELECT month FROM recent_months)
        GROUP BY month
        ORDER BY month DESC
    """), engine)

    def _row(i):
        return scoped.iloc[i] if len(scoped) > i else None

    cur, prev = _row(0), _row(1)

    def _pct_delta(cur_val, prev_val):
        if prev is None or not prev_val:
            return None
        return (cur_val - prev_val) / prev_val * 100

    def _dir(delta):
        return None if delta is None else ("up" if delta >= 0 else "down")

    def _fmt(delta):
        return "no prior month to compare" if delta is None else f"{abs(delta):.0f}% vs last month"

    cur_on_time = (cur["total"] - cur["delayed"]) / cur["total"] * 100 if cur["total"] else 0
    prev_on_time = ((prev["total"] - prev["delayed"]) / prev["total"] * 100) if (prev is not None and prev["total"]) else None

    value_delta = _pct_delta(cur["purchase_value"], prev["purchase_value"] if prev is not None else None)
    delayed_delta = _pct_delta(cur["delayed"], prev["delayed"] if prev is not None else None)
    cycle_delta = _pct_delta(cur["avg_cycle_days"], prev["avg_cycle_days"] if prev is not None else None)
    on_time_delta = _pct_delta(cur_on_time, prev_on_time)

    # items_at_risk: reuses the already-connected stock() query.
    stock_df = stock()
    at_risk = int((stock_df["stock_status"] == "Below reorder").sum())

    # open_imports: business-rule placeholder -- terminal states are
    # 'Arrived at Works' and 'Order Cancelled'; everything else is open.
    imp = pd.read_sql(text("""
        SELECT COUNT(*) AS n FROM public.import_details
        WHERE current_status NOT IN ('Arrived at Works', 'Order Cancelled')
    """), engine)
    open_n = int(imp.iloc[0]["n"])

    return {
        "purchase_value": {
            "value": float(cur["purchase_value"]), "delta": _fmt(value_delta),
            "direction": _dir(value_delta), "good_when": "up",
        },
        "avg_cycle_time": {
            "value": f"{cur['avg_cycle_days']:.1f} days", "delta": _fmt(cycle_delta),
            "direction": _dir(cycle_delta), "good_when": "down",
        },
        "delayed_orders": {
            "value": int(cur["delayed"]), "delta": _fmt(delayed_delta),
            "direction": _dir(delayed_delta), "good_when": "down",
        },
        "on_time_rate": {
            "value": f"{cur_on_time:.0f}%", "delta": _fmt(on_time_delta),
            "direction": _dir(on_time_delta), "good_when": "up",
        },
        "items_at_risk": {
            "value": at_risk, "delta": "current snapshot", "direction": None, "good_when": "down",
        },
        "open_imports": {
            "value": open_n, "delta": "current snapshot", "direction": None, "good_when": "down",
        },
    }


def health():
    """Real health banner, derived from this (most recent) month's delayed rate.

    NOTE: thresholds are a placeholder business rule (same spirit as the
    delay/reorder rules elsewhere in this module) until the business
    defines real SLA bands: <15% delayed = healthy, 15-30% = watch, else risk.
    """
    df = pd.read_sql(text("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN required_d IS NOT NULL AND purchase > required_d THEN 1 ELSE 0 END) AS delayed
        FROM public.purchases_data
        WHERE purchase IS NOT NULL
          AND DATE_TRUNC('month', purchase) = (SELECT MAX(DATE_TRUNC('month', purchase)) FROM public.purchases_data WHERE purchase IS NOT NULL)
    """), get_engine())
    total, delayed = int(df.iloc[0]["total"]), int(df.iloc[0]["delayed"])
    rate = delayed / total * 100 if total else 0

    if rate < 15:
        return {"level": "healthy", "message": f"Supply chain healthy — {delayed} delayed orders this month ({rate:.0f}%)"}
    if rate < 30:
        return {"level": "watch", "message": f"Supply chain stable — {delayed} delayed orders this month ({rate:.0f}%) need attention"}
    return {"level": "risk", "message": f"Supply chain at risk — {delayed} delayed orders this month ({rate:.0f}%)"}


def supplier_performance():
    """Real on-time % per supplier, top suppliers by order volume.

    NOTE: limited to suppliers with >=5 orders and the top 8 by volume, so
    a single-order supplier can't show a misleading 0%/100%. Adjust the
    threshold once the business defines a minimum sample size.
    """
    query = text("""
        SELECT
            supplier,
            100.0 * SUM(CASE WHEN required_d IS NOT NULL AND purchase > required_d
                              THEN 0 ELSE 1 END) / COUNT(*) AS on_time_pct
        FROM public.purchases_data
        WHERE supplier IS NOT NULL AND supplier <> ''
        GROUP BY supplier
        HAVING COUNT(*) >= 5
        ORDER BY COUNT(*) DESC
        LIMIT 8
    """)
    return pd.read_sql(query, get_engine())


def status_split(kind="purchases"):
    """Real composition for donut charts (imports & purchases).

    Uses the same derived/real status the tables use, so the donut always
    matches the table above it. Other kinds still fall back to stub.
    """
    if kind == "imports":
        query = text("""
            SELECT current_status AS label, COUNT(*) AS n
            FROM public.import_details
            WHERE current_status IS NOT NULL AND current_status <> ''
            GROUP BY current_status
            ORDER BY n DESC
        """)
        df = pd.read_sql(query, get_engine())
        return df["label"].tolist(), df["n"].tolist()

    if kind == "purchases":
        query = text("""
            SELECT
                CASE
                    WHEN purchase IS NULL THEN 'Pending'
                    WHEN required_d IS NOT NULL
                         AND purchase > required_d THEN 'Delayed'
                    ELSE 'Completed'
                END AS label,
                COUNT(*) AS n
            FROM public.purchases_data
            GROUP BY label
            ORDER BY n DESC
        """)
        df = pd.read_sql(query, get_engine())
        return df["label"].tolist(), df["n"].tolist()

    return _src.get_status_split(kind=kind)


def aging():
    """Real 'days late' distribution for delayed purchase orders.

    NOTE: purchases_data has zero rows with `purchase IS NULL` in the
    current extract, so there's no real "pending order" population to age
    (see dashboard_kpis_rich NOTE). This chart is repurposed to show how
    late the *delayed* orders were, reusing the aging_buckets component's
    existing bucket boundaries/severity colors (0-30/31-60/61-90/90+ days)
    unchanged -- only the meaning (pending age -> days overdue) changes.
    See dashboard.py's section header for the matching relabel.
    """
    query = text("""
        SELECT
            CASE
                WHEN (purchase - required_d) <= 30 THEN '0-30 days'
                WHEN (purchase - required_d) <= 60 THEN '31-60 days'
                WHEN (purchase - required_d) <= 90 THEN '61-90 days'
                ELSE '90+ days'
            END AS bucket,
            COUNT(*) AS orders
        FROM public.purchases_data
        WHERE required_d IS NOT NULL AND purchase > required_d
        GROUP BY bucket
    """)
    return pd.read_sql(query, get_engine())
