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


def _filtered(df, col, value):
    """Apply one filter value to df[col] -- value can be 'All'/None (no
    filter), a single value (equality, kept for any leftover single-select
    call sites), or a list/tuple/set (multi-select: isin()). Every page
    filter now goes through this so a filter widget can offer "pick more
    than one branch/supplier/etc." without each of the ~30 filter sites
    below needing its own list-handling logic.
    """
    if value is None or value == "All":
        return df
    if isinstance(value, (list, tuple, set)):
        if not value:
            return df
        return df[df[col].isin(value)].reset_index(drop=True)
    return df[df[col] == value].reset_index(drop=True)


# --- Dashboard -------------------------------------------------------
def dashboard_kpis():
    return _src.get_dashboard_kpis()


def purchases_asof():
    """Real max purchase date currently in the data."""
    df = pd.read_sql(text("SELECT MAX(purchase) AS d FROM public.purchases_data WHERE purchase IS NOT NULL"),
                      get_engine())
    return df.iloc[0]["d"]


def weekly_trend():
    """Real weekly buckets from purchases_data — feeds the Dashboard's main
    trend line and the KPI sparklines.

    NOTE: the current extract spans ~1 month, so this is a handful of real
    points (however many ISO weeks exist in the data), not a fabricated
    smooth series. `ui.kpi_card`'s sparkline renders nothing if it gets
    fewer than 2 points, so a thin extract degrades gracefully.

    `week`::date -- without the cast, DATE_TRUNC's raw TIMESTAMP comes back
    through this driver/pandas shifted by the local UTC offset (a week
    starting Monday lands on the preceding Sunday once made tz-naive).
    Casting to a plain date in SQL avoids the tz reinterpretation
    entirely, rather than trying to correct it after the fact.
    """
    query = text("""
        SELECT
            DATE_TRUNC('week', purchase)::date AS week,
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
    n_oos = int((stock_df["stock_status"] == "Out of Stock").sum())
    if n_oos:
        out.append({"level": "high", "message": f"{n_oos} items out of stock"})
    n_below = int((stock_df["stock_status"] == "Below Reorder").sum())
    if n_below:
        out.append({"level": "medium", "message": f"{n_below} items below their reorder level"})

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
def purchases(status="All", supplier="All", branch="All", category="All", mop="All", sourcing_officer="All"):
    """Real data: purchase orders joined to item names + category/material
    (from `items`), with a derived status.

    purchases_data has no status column, so it is derived from the dates:
      - no purchase date yet                      -> 'Pending'
      - purchased after the required date         -> 'Delayed'
      - otherwise                                 -> 'Completed'

    NOTE: this is a placeholder business rule (like the stock reorder rule).
    If the business defines delay differently (e.g. vs ppc_store date, or a
    grace period), only this CASE expression changes — the page stays as is.

    `material` (items.material_standard) is real but sparse (~33% of rows)
    -- returned as a column for search/table, not offered as its own filter
    dropdown since two-thirds of rows would just show as unmatched.

    `item_code` (2026-07-22): added so the Reports builder can join
    Purchases to Inventory (`stock()` already returns item_code) -- the two
    are the only sources sharing a real item-level key.
    """
    query = text("""
        SELECT
            p.ref_no,
            p.po_number,
            p.supplier,
            p.item_code,
            COALESCE(i.item, p.item_code) AS item,
            p.branch,
            i.item_category,
            i.material_standard AS material,
            p.qty,
            p.amount,
            p.required_d AS required_date,
            p.purchase   AS purchase_date,
            p.ppc_store,
            p.mop,
            p.bill_no,
            p.sourcing_o AS sourcing_officer,
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

    df = _filtered(df, "status", status)
    df = _filtered(df, "supplier", supplier)
    df = _filtered(df, "branch", branch)
    df = _filtered(df, "item_category", category)
    df = _filtered(df, "mop", mop)
    df = _filtered(df, "sourcing_officer", sourcing_officer)
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


def purchases_branch_list():
    query = text("""
        SELECT DISTINCT branch FROM public.purchases_data
        WHERE branch IS NOT NULL AND branch <> '' ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["branch"].tolist()


def purchases_category_list():
    query = text("""
        SELECT DISTINCT i.item_category
        FROM public.purchases_data p JOIN public.items i ON i.item_code = p.item_code
        WHERE i.item_category IS NOT NULL AND i.item_category <> '' ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["item_category"].tolist()


def purchases_mop_list():
    query = text("SELECT DISTINCT mop FROM public.purchases_data WHERE mop IS NOT NULL AND mop <> '' ORDER BY 1")
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["mop"].tolist()


def purchases_sourcing_officer_list():
    query = text("""
        SELECT DISTINCT sourcing_o FROM public.purchases_data
        WHERE sourcing_o IS NOT NULL AND sourcing_o <> '' ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["sourcing_o"].tolist()


def purchase_status_list():
    """Real distinct purchase statuses, derived the same way purchases()
    computes 'status' -- not hardcoded. The old hardcoded filter list
    (All/Pending/Completed/Delayed) included 'Pending' even though the
    current extract has zero rows with purchase IS NULL (every order
    already has a completion date), so picking it always silently emptied
    the page. Deriving this dynamically means the filter can never offer
    an option that doesn't exist in the data -- if Pending orders show up
    in a future extract, this list picks them up automatically.
    """
    query = text("""
        SELECT DISTINCT
            CASE
                WHEN purchase IS NULL THEN 'Pending'
                WHEN required_d IS NOT NULL AND purchase > required_d THEN 'Delayed'
                ELSE 'Completed'
            END AS status
        FROM public.purchases_data
        ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["status"].tolist()


# --- Inventory -------------------------------------------------------
def stock(status="All", category="All", branch="All"):
    """Real data: current stock joined to item names AND full item detail
    (category, unit of measure, specs, group, material standard) from
    `items`, with a computed status and a real (not fabricated) reorder
    formula.

    The stock table has no item name (it's in `items`) and no stored status,
    so we join for the name and derive `stock_status` here. This keeps the
    return shape identical to what the Inventory page expects, so the page
    does not change.

    `item_category` / `uom` / `specs` have solid real coverage (~93-100% of
    26,818 items); `group_name` / `material_standard` are real but much
    sparser (~13-32%) -- all four are still returned so a search hit shows
    everything actually on file for that item, not just name/branch/qty.

    Status tiers, business's real formula (confirmed 2026-07-21, and matches
    what the teammate's own chatbot backend documents independently):
        avg_daily_issuance = issuance_3m / 90
        safety_stock  = avg_daily_issuance * safety_days
        reorder_level = avg_daily_issuance * (lead_time_days + safety_days)
      - 'Out of Stock': available_qty <= 0.
      - 'Below Reorder': 0 < available_qty < reorder_level.
      - 'OK': everything else.
    `safety_days` / `lead_time_days` come from `ab_items` (item_code +
    branch_name, provided by the business 2026-07-21 -- not every item has
    a row here, ~91% coverage against `stock` at load time). Where an item
    has no ab_items row, reorder_level is left NaN rather than guessed at,
    so it can only ever land in Out of Stock / OK, same as before this
    formula existed -- no item is silently misclassified.

    `avg_daily_issuance` / `days_of_stock` (available_qty / avg_daily_issuance)
    are both real, computed from actual issuance history (public.issuance,
    item_code + branch) -- `days_of_stock` is NaN where an item has no
    recent issuance to estimate a runway from (honest, not a missing-data
    bug).
    """
    query = text("""
        WITH issuance_3m AS (
            SELECT item_code, branch, SUM(quantity) AS issuance_3m_qty
            FROM public.issuance
            WHERE from_date >= CURRENT_DATE - INTERVAL '90 days'
            GROUP BY item_code, branch
        )
        SELECT
            s.item_code,
            COALESCE(i.item, s.item_code) AS item,
            s.branch,
            s.stock_qty,
            s.available_qty,
            s.hold_qty,
            i.item_category,
            i.uom,
            i.specs,
            i.group_name,
            i.material_standard,
            iss.issuance_3m_qty,
            ab.safety_days,
            ab.lead_time_days
        FROM public.stock s
        LEFT JOIN public.items i ON i.item_code = s.item_code
        LEFT JOIN issuance_3m iss ON iss.item_code = s.item_code AND iss.branch = s.branch
        LEFT JOIN public.ab_items ab ON ab.item_code = s.item_code AND ab.branch_name = s.branch
        ORDER BY s.item_code
    """)
    df = pd.read_sql(query, get_engine())

    df["avg_daily_issuance"] = df["issuance_3m_qty"] / 90
    df["days_of_stock"] = df["available_qty"] / df["avg_daily_issuance"]
    df.loc[~pd.notna(df["avg_daily_issuance"]) | (df["avg_daily_issuance"] == 0), "days_of_stock"] = pd.NA

    df["safety_stock"] = df["avg_daily_issuance"] * df["safety_days"]
    df["reorder_level"] = df["avg_daily_issuance"] * (df["lead_time_days"] + df["safety_days"])

    def _status(row):
        if row["available_qty"] <= 0:
            return "Out of Stock"
        if pd.notna(row["reorder_level"]) and row["available_qty"] < row["reorder_level"]:
            return "Below Reorder"
        return "OK"

    df["stock_status"] = df.apply(_status, axis=1)

    df = _filtered(df, "stock_status", status)
    df = _filtered(df, "item_category", category)
    df = _filtered(df, "branch", branch)
    return df


def inventory_branch_list():
    query = text("SELECT DISTINCT branch FROM public.stock WHERE branch IS NOT NULL AND branch <> '' ORDER BY 1")
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["branch"].tolist()


def inventory_category_list():
    """Real distinct item_category values that actually appear in stock
    (not all 34 categories in `items` necessarily have stock on hand)."""
    query = text("""
        SELECT DISTINCT i.item_category
        FROM public.stock s
        JOIN public.items i ON i.item_code = s.item_code
        WHERE i.item_category IS NOT NULL AND i.item_category <> ''
        ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["item_category"].tolist()


# --- Imports ---------------------------------------------------------
# Two real, defensible normalizations (checked against actual distinct
# values, 2026-07-22) -- kept as shared SQL fragments so the main query and
# the filter-list helpers can never drift out of sync with each other:
#   - branch: 'QBl-II' (4 rows) vs 'QBL-II' (85 rows) is the same branch,
#     typed with inconsistent casing -- UPPER() is an unambiguous fix, no
#     guessing involved.
#   - mode_of_shipment: 'Sea'/'By Sea' (287+70 rows) and 'Air'/'By Air'/
#     'By  Air' (double-space typo; 53+7+1 rows) are the same two real
#     modes spelled differently. NOT touched: ~13 rows where a container
#     spec ("1 x 20' OT") was entered in this field instead -- inferring
#     those as "Sea" would be a guess, not a normalization, so they're left
#     exactly as they are in the source.
def _branch_norm_sql(col):
    return f"CASE WHEN UPPER({col}) = 'QBL-II' THEN 'QBL-II' ELSE {col} END"


def _mode_of_shipment_norm_sql(col):
    return f"""CASE
            WHEN TRIM(REGEXP_REPLACE({col}, '\\s+', ' ', 'g')) IN ('Sea', 'By Sea') THEN 'Sea'
            WHEN TRIM(REGEXP_REPLACE({col}, '\\s+', ' ', 'g')) IN ('Air', 'By Air') THEN 'Air'
            ELSE {col}
        END"""


def imports(status="All", branch="All", supplier="All", customer="All", country="All", category="All",
            shipping_line="All", mode_of_shipment="All", bank="All"):
    """Real data: import shipments from import_details, enriched with the
    matching shipment_details (logistics side: ETD, shipping line, mode of
    shipment, clearance mode) and payment_history (bank, payment mode) rows
    -- both confirmed 1:1 with import_details by import_id (451 rows each,
    no fan-out risk from the LEFT JOINs).

    `current_status` is the real workflow state (10 distinct business values
    such as 'Arrived at Works', 'In Transit', 'Under Custom Clearance').

    NOTE: total_value_pkr is often 0 in the source (value is recorded in
    total_value_fc / foreign currency); both are returned so the page/team
    can decide which to display once an FX rule is provided.

    Checked and deliberately left OUT (2026-07-21): docs_status (449/451
    NULL), gin_status (100% NULL) -- neither can support a real filter.
    `currency` no longer exists on payment_history (schema changed since
    it was last checked; ex_rate is what's there now).

    `branch` and `mode_of_shipment` are normalized (see _branch_norm_sql() /
    _mode_of_shipment_norm_sql() above) -- casing/spelling duplicates only,
    never a guessed-at value.
    """
    query = text(f"""
        SELECT
            d.import_ref,
            {_branch_norm_sql("d.branch")} AS branch,
            d.customer,
            d.supplier,
            d.supplier_country,
            d.category,
            d.total_wt_ton,
            d.total_value_fc,
            d.total_value_pkr,
            d.demand_date,
            d.req_date,
            d.gin_date,
            d.current_status,
            sd.etd,
            sd.eta_final,
            sd.s_line AS shipping_line,
            {_mode_of_shipment_norm_sql("sd.mode_of_shipment")} AS mode_of_shipment,
            sd.clearance_mode,
            ph.bank,
            ph.payment_mode
        FROM public.import_details d
        LEFT JOIN public.shipment_details sd ON sd.import_id = d.import_id
        LEFT JOIN public.payment_history ph ON ph.import_id = d.import_id
        ORDER BY d.import_id
    """)
    df = pd.read_sql(query, get_engine())

    df = _filtered(df, "current_status", status)
    df = _filtered(df, "branch", branch)
    df = _filtered(df, "supplier", supplier)
    df = _filtered(df, "customer", customer)
    df = _filtered(df, "supplier_country", country)
    df = _filtered(df, "category", category)
    df = _filtered(df, "shipping_line", shipping_line)
    df = _filtered(df, "mode_of_shipment", mode_of_shipment)
    df = _filtered(df, "bank", bank)
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


def _imports_distinct(column):
    query = text(f"""
        SELECT DISTINCT {column} FROM public.import_details
        WHERE {column} IS NOT NULL AND {column} <> '' ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df[column].tolist()


def imports_branch_list():
    query = text(f"""
        SELECT DISTINCT {_branch_norm_sql("branch")} AS branch FROM public.import_details
        WHERE branch IS NOT NULL AND branch <> '' ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["branch"].tolist()


def imports_supplier_list():
    return _imports_distinct("supplier")


def imports_customer_list():
    return _imports_distinct("customer")


def imports_country_list():
    return _imports_distinct("supplier_country")


def imports_category_list():
    """Real distinct categories that appear in import_details.

    'Hammad Cukurova' (3/451 rows, checked 2026-07-22) is excluded here --
    it reads as a supplier/company name, not a category (real values are
    Store/Engg./Sample/Capital/Refurb./Trading/Scraps), almost certainly
    the wrong value landed in the wrong column. The raw column itself is
    untouched -- those 3 rows are still visible in search/the full table --
    this only stops a clearly-wrong value from being offered as something
    to filter BY. Flagged for the business to correct at the source; not
    guessed at or silently rewritten.
    """
    query = text("""
        SELECT DISTINCT category FROM public.import_details
        WHERE category IS NOT NULL AND category <> '' AND category <> 'Hammad Cukurova'
        ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["category"].tolist()


def imports_shipping_line_list():
    query = text("""
        SELECT DISTINCT s_line FROM public.shipment_details
        WHERE s_line IS NOT NULL AND s_line <> '' ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["s_line"].tolist()


def imports_mode_of_shipment_list():
    query = text(f"""
        SELECT DISTINCT {_mode_of_shipment_norm_sql("mode_of_shipment")} AS mode_of_shipment
        FROM public.shipment_details
        WHERE mode_of_shipment IS NOT NULL AND mode_of_shipment <> '' ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["mode_of_shipment"].tolist()


def imports_bank_list():
    query = text("""
        SELECT DISTINCT bank FROM public.payment_history
        WHERE bank IS NOT NULL AND bank <> '' ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["bank"].tolist()



# --- Logistics ---------------------------------------------------------
# Export-only (2026-07-21): Logistics covers the export shipping pipeline --
# shipments, packing, inland transport/shifting, documentation -- NOT
# imports. Import shipment tracking already has its own tab (Imports,
# import_details); Logistics' four views below map to the business's own
# stages: export_shipments, packing_details, shifting_movements,
# export_documents (+ exports as the shipment header).
#
# Several of the pre-built metric views mentioned in earlier notes turned
# out to have real data-quality problems on inspection (2026-07-21) --
# NOT used here, and flagged rather than silently charted:
#   - v_shifting_metrics.transit_days: every value is around -20,500 (a
#     ~56-year negative offset) -- clearly a broken calculation upstream.
#   - v_shipment_metrics.transit_days: always exactly 0 across all 120
#     non-null rows -- looks like a same-value bug, not real transit time.
#   - v_packing_metrics: on_time_packing (and every other metric column)
#     is NULL on 100% of its 1,375 rows -- the view appears to never
#     populate. packing_details.target_packing_date is also 100% NULL, so
#     "on-time packing" can't be derived here either; used target_rfd /
#     actual_rfd_date instead (real coverage: 490 / 641 of 1,375 rows).
# v_shipment_metrics.total_logistics_cost/cost_per_kg and
# v_shifting_metrics.savings_rs DID check out as real, sane values and are
# used below.
def logistics_shipments(status="All", stage="All", shipping_line="All", country="All"):
    """Real data: export shipments (public.export_shipments), the shipment-
    batch grain (165 rows -- a handful of exports have 2+ batches, so this
    is finer-grained than `exports` itself). LEFT JOINs exports for
    customer/agent context and v_shipment_metrics for real cost fields.

    50 of 165 rows have no export_id yet (shipment tracked before a formal
    export record exists) -- kept via LEFT JOIN rather than dropped, since
    that's real, current pipeline state, not bad data.

    shipment_terms (64% coverage, 5 real values) and etd_karachi (81%
    coverage) added 2026-07-21 -- both real, previously not selected.
    """
    query = text("""
        SELECT
            es.shipment_id, es.export_id,
            e.exp_no, e.customer, e.shipping_agent, e.payment_term,
            es.country, es.pod, es.shipment_stage, es.shipment_status,
            es.shipment_terms, es.etd_karachi,
            es.net_weight_kgs, es.gross_weight_kgs,
            es.s_agent, es.c_agent, es.s_line,
            es.port_in_date, es.actual_arrival_date, es.cut_off_date,
            es.quoted_sea_freight, es.actual_sea_freight, es.clearance_cost,
            vm.total_logistics_cost, vm.cost_per_kg,
            COALESCE(es.shipment_status, 'Unknown') AS status
        FROM public.export_shipments es
        LEFT JOIN public.exports e ON e.export_id = es.export_id
        LEFT JOIN public.v_shipment_metrics vm ON vm.shipment_id = es.shipment_id
        ORDER BY es.shipment_id DESC
    """)
    df = pd.read_sql(query, get_engine())
    df = _filtered(df, "status", status)
    df = _filtered(df, "shipment_stage", stage)
    df = _filtered(df, "s_line", shipping_line)
    df = _filtered(df, "country", country)
    return df


def logistics_shipment_status_list():
    query = text("""
        SELECT DISTINCT COALESCE(shipment_status, 'Unknown') AS status
        FROM public.export_shipments ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["status"].tolist()


def _logistics_shipments_distinct(column):
    query = text(f"""
        SELECT DISTINCT {column} FROM public.export_shipments
        WHERE {column} IS NOT NULL AND {column} <> '' ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df[column].tolist()


def logistics_shipment_stage_list():
    return _logistics_shipments_distinct("shipment_stage")


def logistics_shipping_line_list():
    return _logistics_shipments_distinct("s_line")


def logistics_shipment_country_list():
    return _logistics_shipments_distinct("country")


def logistics_packing(status="All", works="All", product_category="All", business_type="All"):
    """Real data: packing_details (1,375 rows). `status` uses
    `overall_status` (clean: 'Pending Packing' / 'In Progress' only) rather
    than the richer but messy `packing_status` free-text field (real values
    include inconsistent case/spacing like 'Gate Out' vs 'Gate out' vs
    'Gateout', and a couple of rows where the source data literally has a
    date string in that column) -- packing_status is still returned as a
    raw column for the search table, just not used to drive the filter.

    rfd_delay_days (actual_rfd_date - target_rfd) is computed here from
    real dates; target_packing_date is 100% NULL in the source so an
    "on-time packing" metric can't be derived at all yet.

    `works` (2026-07-21): 100% populated, 15 real values -- a real filter
    candidate that was missed when this view was first built.
    """
    query = text("""
        SELECT
            packing_id, export_id, exp_batch_raw, business_type, product_category,
            customer_type, customer, jobs_no, works, qty, qty_uom, pkgs,
            net_weight_kgs, gross_weight_kgs,
            actual_packing_date, target_rfd, actual_rfd_date,
            packing_status, overall_status,
            quoted_packing_cost, actual_packing_cost,
            COALESCE(overall_status, 'Unknown') AS status
        FROM public.packing_details
        ORDER BY packing_id DESC
    """)
    df = pd.read_sql(query, get_engine())
    df["rfd_delay_days"] = (pd.to_datetime(df["actual_rfd_date"]) - pd.to_datetime(df["target_rfd"])).dt.days
    df = _filtered(df, "status", status)
    df = _filtered(df, "works", works)
    df = _filtered(df, "product_category", product_category)
    df = _filtered(df, "business_type", business_type)
    return df


def _logistics_packing_distinct(column):
    query = text(f"""
        SELECT DISTINCT {column} FROM public.packing_details
        WHERE {column} IS NOT NULL AND {column} <> '' ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df[column].tolist()


def logistics_packing_works_list():
    return _logistics_packing_distinct("works")


def logistics_packing_category_list():
    return _logistics_packing_distinct("product_category")


def logistics_packing_business_type_list():
    return _logistics_packing_distinct("business_type")


def logistics_packing_status_list():
    query = text("""
        SELECT DISTINCT COALESCE(overall_status, 'Unknown') AS status
        FROM public.packing_details ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["status"].tolist()


def logistics_shifting(status="All", movement_type="All", payment_status="All"):
    """Real data: shifting_movements (464 rows) -- inland transport/
    dispatch. `status` uses `operational_status`, filled to 'In Progress'
    where NULL (218/464 rows): the real column has only 'Delivered' as a
    populated value, with no other real label for "not yet delivered" --
    same spirit as other placeholder fills in this module, documented
    rather than left as a silent gap. `tracking_status` mirrors
    `operational_status` exactly in the source, so isn't duplicated here.

    v_shifting_metrics.savings_rs is included (checked sane: real spread,
    -195,900 to 328,600); its transit_days and savings_pct columns are
    NOT included -- see the module-level note above for why. The table's
    own `shipment_status` column was checked too: only 246/464 populated
    AND only 1 distinct value when it is -- not filterable, so it's left
    out entirely rather than offered as a dead-end dropdown.
    """
    query = text("""
        SELECT
            s.shifting_id, s.export_id, s.movement_type, s.execution_date, s.customer,
            s.item_name, s.pickup_point, s.destination, s.province, s.transporter,
            s.gross_weight_kgs, s.vehicle_type, s.no_of_vehicles,
            s.containers_20ft, s.containers_40ft,
            s.actual_freight_rs, s.quoted_freight_rs,
            s.payment_status, s.tracking_status,
            vm.savings_rs,
            COALESCE(s.operational_status, 'In Progress') AS status
        FROM public.shifting_movements s
        LEFT JOIN public.v_shifting_metrics vm ON vm.shifting_id = s.shifting_id
        ORDER BY s.shifting_id DESC
    """)
    df = pd.read_sql(query, get_engine())
    df = _filtered(df, "status", status)
    df = _filtered(df, "movement_type", movement_type)
    df = _filtered(df, "payment_status", payment_status)
    return df


def logistics_movement_type_list():
    query = text("""
        SELECT DISTINCT movement_type FROM public.shifting_movements
        WHERE movement_type IS NOT NULL AND movement_type <> '' ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["movement_type"].tolist()


def logistics_payment_status_list():
    query = text("""
        SELECT DISTINCT payment_status FROM public.shifting_movements
        WHERE payment_status IS NOT NULL AND payment_status <> '' ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["payment_status"].tolist()


def logistics_shifting_status_list():
    query = text("""
        SELECT DISTINCT COALESCE(operational_status, 'In Progress') AS status
        FROM public.shifting_movements ORDER BY 1
    """)
    df = pd.read_sql(query, get_engine())
    return ["All"] + df["status"].tolist()


def logistics_documentation(status="All"):
    """Real data: v_documentation_completion (163 rows, one per export --
    this view DID check out: real varying completion percentages, unlike
    v_packing_metrics). `status` is derived from completion_pct with
    placeholder thresholds (same spirit as the delay/reorder rules
    elsewhere in this module) until the business defines real bands:
    >=95% Complete, >=70% Near Complete, else Incomplete.
    """
    query = text("""
        SELECT
            export_id, exp_no, batch_no, total_documents, completed_documents,
            pending_documents, completion_pct, customs_completion_pct,
            customer_completion_pct, bank_completion_pct,
            missing_customs_documents, missing_customer_documents, missing_bank_documents
        FROM public.v_documentation_completion
        ORDER BY export_id DESC
    """)
    df = pd.read_sql(query, get_engine())

    def _doc_status(pct):
        if pd.isna(pct):
            return "Unknown"
        if pct >= 95:
            return "Complete"
        if pct >= 70:
            return "Near Complete"
        return "Incomplete"

    df["status"] = df["completion_pct"].apply(_doc_status)
    df = _filtered(df, "status", status)
    return df


def logistics_documentation_status_list():
    return ["All", "Complete", "Near Complete", "Incomplete", "Unknown"]


def logistics_document_types():
    """Real line-item document tracking (export_documents, 3,053 rows) --
    document_type x status breakdown. Not filtered by the Documentation
    view's export-level status picker (this is a different grain: one
    export has many documents); the page captions it as covering all
    exports so it isn't misread as scoped to the current filter.
    """
    query = text("""
        SELECT document_type, status, COUNT(*) AS n
        FROM public.export_documents
        WHERE document_type IS NOT NULL
        GROUP BY document_type, status
    """)
    return pd.read_sql(query, get_engine())


# --- Assistant -------------------------------------------------------
def ask_assistant(question, history=None):
    """Real text-to-SQL assistant (chatbot/agent.py): LangGraph + OpenAI
    generates a read-only SQL query against this database, runs it, and
    summarizes the result. Was a hardcoded stub (_src.ask_assistant) until
    2026-07-22 -- now the same engine the Assistant page uses.

    `history` is the previous turn's {"question", "sql"} (or None), for
    follow-ups like "show that as a table" / "sort by X" -- the caller owns
    session state (this module never touches st.session_state), so it's
    passed in rather than read here.

    Returns the engine's native shape: {answer, dataframe, sql, error,
    display, chart_type} -- see chatbot/agent.py's answer_question() for
    what each key means.
    """
    from chatbot.agent import answer_question
    return answer_question(question, history=history)


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

    # items_at_risk: reuses the already-connected stock() query. Now that
    # 'Below Reorder' is a real tier (not just 'Out of Stock'), at-risk
    # covers both -- an item that hasn't hit zero yet but is trending
    # toward it is exactly what this card exists to surface.
    stock_df = stock()
    at_risk = int(stock_df["stock_status"].isin(["Out of Stock", "Below Reorder"]).sum())

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
