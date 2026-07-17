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
    return _src.get_purchase_trend()


def alerts():
    return _src.get_alerts()


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
    return _src.get_dashboard_kpis_rich()


def health():
    return _src.get_health()


def supplier_performance():
    return _src.get_supplier_performance()


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
    return _src.get_aging()
