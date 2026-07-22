"""
chatbot/agent.py — a LangGraph text-to-SQL agent over the supply_chain_db.

Flow (LangGraph):

    generate_sql ──► execute_sql ──► (error & attempts left?) ──► generate_sql
                                   └────────────► summarize ──► END

* generate_sql : OpenAI writes ONE read-only PostgreSQL SELECT from the live
                 schema (and the previous error, when retrying).
* execute_sql  : runs the query read-only, returns a DataFrame or an error.
* summarize    : OpenAI writes a short natural-language answer about the result
                 (skipped for table/chart results, which show the data directly).

Public API:
    answer_question(question, history=None, date_range=None) -> {
        "sql": str, "dataframe": pandas.DataFrame | None, "answer": str,
        "error": str | None, "display": str, "chart_type": str | None,
    }

Config via env (see .env / .env.example):
    OPENAI_API_KEY, OPENAI_MODEL,
    PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
"""

from __future__ import annotations

import json
import os
import re
from datetime import date
from functools import lru_cache
from typing import Any, Optional, TypedDict

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Model + key come straight from the environment / project .env (see .env.example).
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
MAX_ROWS = 100000        # high safety cap injected into generated queries (effectively "all")
MAX_ATTEMPTS = 3         # SQL generation retries on execution error


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db_uri() -> str:
    user = os.getenv("PGUSER", "postgres")
    pwd = os.getenv("PGPASSWORD")
    if not pwd:
        raise RuntimeError(
            "PGPASSWORD is not set. Set it in the environment (e.g. the "
            "project .env file) -- no default password is used here."
        )
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5432")
    db = os.getenv("PGDATABASE", "supply_chain_db")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(get_db_uri(), pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_schema() -> str:
    """CREATE-TABLE statements (plus a couple of sample rows per table) for the LLM
    prompt.

    sample_rows_in_table_info is kept low (2): sample rows help the model match real
    value formats, but each one adds tokens to every SQL-generation call, so we cap
    it to keep generation fast/cheap — the system prompt already documents the tricky
    columns and their value formats."""
    from langchain_community.utilities import SQLDatabase
    db = SQLDatabase(get_engine(), sample_rows_in_table_info=2)
    return db.get_table_info()


# ---------------------------------------------------------------------------
# SQL safety helpers
# ---------------------------------------------------------------------------

_WRITE_WORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|"
    r"comment|merge|replace|call|do|copy|vacuum)\b",
    re.IGNORECASE,
)


def _first_statement(s: str) -> str:
    """Return everything up to the first TOP-LEVEL semicolon — one that is not
    inside a single-quoted string literal. A naive s.split(';')[0] truncates a
    query at a semicolon inside a string (e.g. a note column or ILIKE '%a;b%'),
    producing invalid SQL; this walks the string and skips quoted regions
    (including the SQL '' escape for a literal quote)."""
    in_str = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "'":
            if in_str and i + 1 < len(s) and s[i + 1] == "'":  # '' escaped quote
                i += 2
                continue
            in_str = not in_str
        elif ch == ";" and not in_str:
            return s[:i]
        i += 1
    return s


def clean_sql(raw: str) -> str:
    """Strip markdown fences / prose and keep the first statement."""
    s = raw.strip()
    s = re.sub(r"^```(?:sql)?", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"```$", "", s).strip()
    # keep only the first statement (semicolons inside string literals don't count)
    s = _first_statement(s).strip()
    return s


def is_safe_select(sql: str) -> bool:
    stripped = sql.lstrip().lower()
    return stripped.startswith(("select", "with")) and not _WRITE_WORDS.search(sql)


def add_limit(sql: str, limit: int = MAX_ROWS) -> str:
    if re.search(r"\blimit\b", sql, re.IGNORECASE):
        return sql
    return f"{sql}\nLIMIT {limit}"


def dedupe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Make column names unique. A SELECT * across joined tables can return
    repeated names (e.g. import_id, item_code, uom), which pandas allows but
    Streamlit/Arrow rejects. Later duplicates get a _1, _2 … suffix."""
    if not df.columns.duplicated().any():
        return df
    seen: dict = {}
    new_cols = []
    for col in df.columns:
        if col in seen:
            seen[col] += 1
            new_cols.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            new_cols.append(col)
    df = df.copy()
    df.columns = new_cols
    return df


# ---------------------------------------------------------------------------
# Display intent — decide what the user wants back (text / table / chart)
# ---------------------------------------------------------------------------
_CHART_RE = re.compile(
    r"\b(charts?|graphs?|plots?|pies?|donuts?|bars?|lines?|trends?|"
    r"visuali[sz]e|histograms?)\b", re.I
)
_TABLE_RE = re.compile(
    r"\b(tables?|lists?|rows|records|csv|spreadsheets?|breakdowns?)\b"
    r"|\b(show|list|give)\s+(me\s+)?all\b",
    re.I,
)


def detect_display(question: str):
    """Return (mode, chart_type). mode is 'text' | 'table' | 'chart'.
    Default is 'text' (describe only) unless the user explicitly asks for a
    table or a chart."""
    q = question or ""
    if _CHART_RE.search(q):
        ql = q.lower()
        if "pie" in ql or "donut" in ql:
            return "chart", "pie"
        if "line" in ql or "trend" in ql or "over time" in ql:
            return "chart", "line"
        return "chart", "bar"
    if _TABLE_RE.search(q):
        return "table", None
    return "text", None


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No OpenAI API key found. Set OPENAI_API_KEY in the environment "
            "(e.g. the project .env file)."
        )
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        temperature=0,
        max_tokens=4096,          # was unset — long queries were being truncated
        api_key=api_key,
    )


_SQL_SYSTEM = """You are a senior PostgreSQL analyst for a supply-chain database. Write exactly ONE
read-only SQL query (a single SELECT, optionally a leading WITH) that answers the
question. Return ONLY the SQL — no explanation, no markdown fences, no trailing semicolon.

OUTPUT & SAFETY
- PostgreSQL dialect, read-only: never INSERT/UPDATE/DELETE/DDL. Never return HTML.
- Use only tables/columns in the schema below. Prefer explicit columns over SELECT *.
- Case-insensitive text filters (ILIKE '%value%'); match actual DB column values.
- For "all"/"list" questions cap with LIMIT {max_rows} unless a specific number is asked.
- Keep the SQL as SHORT as correctly possible. Compute a value ONCE (in a CTE) and reuse
  it — never repeat the same CASE/subexpression in multiple places (e.g. do the unit
  conversion once in a CTE, not again inside a COUNT(...) FILTER). Avoid long multi-branch
  status CASEs — one short note (or omit it) is enough.

ITEMS & PRODUCTS
- `item_code` is an opaque code (e.g. '26487-60'), NOT a product name. Transaction tables
  (stock, issuance, import_item, purchases_data, store_requisition) carry only item_code;
  the readable name/specs are in `items` (item, group_name, material_standard,
  item_category, specs). When the user names a product/material/keyword (pipe, resin,
  steel, bearing), JOIN the transaction table to items ON item_code and filter with ILIKE
  on items.item (and those descriptive columns). NEVER put a product name in an item_code
  filter. Example — "supplier of our last purchase of resin":
      SELECT p.purchase, p.supplier
      FROM purchases_data p JOIN items i ON p.item_code = i.item_code
      WHERE i.item ILIKE '%resin%' ORDER BY p.purchase DESC NULLS LAST LIMIT 1
- Multi-word product names are often SPLIT across columns — base name in items.item,
  variant/grade in items.specs (e.g. "Hard Coke Anode Butt" = item 'Hard Coke',
  specs 'Anode Butt'). Do NOT require the whole phrase contiguously in one column;
  require EACH WORD to appear somewhere in the combined descriptive text:
     WHERE (coalesce(i.item,'')||' '||coalesce(i.group_name,'')||' '||
            coalesce(i.material_standard,'')||' '||coalesce(i.item_category,'')||' '||
            coalesce(i.specs,'')) ILIKE '%hard%'
       AND (…same blob…) ILIKE '%coke%' AND (…) ILIKE '%anode%' AND (…) ILIKE '%butt%'
- Prefer showing item specs/name over raw item_code in results. When showing a quantity or
  stock, append the item's uom (from items.uom).

STOCK / INVENTORY (stock table: one row per item_code+branch; available_qty = on hand)
- Count PER STOCK ROW (each item+branch position), NOT summed per item — stock is tracked by
  branch, so every item-branch position counts on its own.
- "OUT OF STOCK" = stock rows with available_qty <= 0, counted per row:
      SELECT COUNT(*) FROM stock WHERE available_qty <= 0     (each empty item-branch position).
  Do NOT sum an item's branches together, and do NOT LEFT JOIN the items master. Counting from
  the stock table already excludes never-carried items (they have no stock row). "with/without
  duplicates" does not change this — every empty row counts.
- "in stock / on hand" = stock rows with available_qty > 0.
- ONLY if the user clearly wants DISTINCT ITEMS that are out of stock in ALL branches (no stock
  anywhere) use the per-item form instead: item_code GROUP BY having SUM(available_qty) <= 0 —
  a smaller figure; say which basis you used.
- "NOT STOCKED / not carried" = item has NO stock row at all (NOT EXISTS in stock) — a
  DIFFERENT, much larger set; keep it separate from out-of-stock.

SUPPLIERS
- Supplier names can contain product-like words (e.g. 'Muhammad Younas Nut Bolt',
  'Al-Rehman Steel'). When the user names a supplier (usually after by/from/supplier/
  vendor), treat the WHOLE phrase as the supplier and filter ONLY the supplier column.
  Do NOT also add an item filter from words in the supplier's name. Only filter items when
  the user names a product SEPARATELY, e.g. "steel bolts from Muhammad Younas Nut Bolt" ->
  supplier ILIKE '%younas%' AND item ILIKE '%steel bolt%'.
- MATCH ROBUSTLY — the user's spelling rarely matches the stored value exactly, and pasting
  the raw phrase into one ILIKE is the #1 cause of false-empty results. Instead:
    * Prefer the most distinctive token: "orders by Muhammad Younas Nut Bolt" ->
      supplier ILIKE '%younas%'.
    * When the name has no distinctive token (generic words like Corporation/Traders/
      Trading/Industries/Enterprises, or repeated letters), match on the whole phrase with
      SPACES AND PUNCTUATION IGNORED on BOTH sides — strip the column with
      regexp_replace(lower(supplier),'[^a-z0-9]','','g') and strip the user's phrase to the
      same form. e.g. "aa corporations" -> regexp_replace(lower(supplier),'[^a-z0-9]','','g')
      ILIKE '%aacorporation%'. This makes 'aa corporation' match the stored 'A A CORPORATION'.
    * IGNORE a trailing plural 's' the user may add ("corporations" must still match
      "corporation") — strip it from the comparison literal.
- A supplier can be a LOCAL vendor OR an import supplier: the same name may live in
  purchases_data.supplier (local purchases) and/or import_details.supplier (imports), and
  MANY vendors appear ONLY in purchases_data. So for a supplier's "orders/purchases", do NOT
  assume imports — querying import_details alone is a common false-negative. If the question
  is not explicitly about imports/shipments/ETAs, use purchases_data (local orders). When it
  could be either, UNION both so nothing is missed:
     SELECT 'Local'  AS src, ref_no AS ref, purchase AS order_date, required_d, amount, supplier
     FROM purchases_data WHERE <robust supplier match>
     UNION ALL
     SELECT 'Import', import_ref, demand_date, req_date, total_value_pkr, supplier
     FROM import_details WHERE <robust supplier match>

UNITS (UOM) — governs OUTPUT AGGREGATION only, NEVER a join/filter
- JOIN on item_code ONLY. NEVER compare uom in a JOIN or WHERE (no "ii.uom = i.uom"):
  uom strings are inconsistent (items.uom='kg' but import_item.uom may be 'Kgs'/'Ton'/'MT'),
  so matching on them silently drops every row. items.uom is the canonical display unit.
  Ignore import_item.uom for JOINS and DISPLAY, but you MUST use it to CONVERT
  import_item.qty to the item's unit before any arithmetic with it (see IMPORT UNIT
  CONVERSION).
- Do NOT SUM/AVG a physical QUANTITY (stock_qty, available_qty, issuance quantity, import
  qty…) across rows whose items.uom differ — kg + Ltr is meaningless. If a keyword spans
  multiple items.uom, break down per uom (GROUP BY i.uom) or restrict to one item/uom;
  treat NULL uom as its own 'unknown' unit. Money (amount, *_value_pkr, total_price) CAN be
  summed across uoms. Stock cost/amount is in PKR.

DOMAINS — two separate worlds, never joined to each other
- IMPORTS: import_details, import_item, shipment_details (the import shipment table, one row
  per batch/BL, linked via import_details.import_id), payment_history.
- EXPORTS/logistics: exports, export_shipments, export_documents, shipment_containers,
  packing_details, shifting_movements.
  Their id columns are unrelated — joining across the two domains is always wrong.

IMPORT STATUS & TIMING
- Progress = import_details.current_status ('Arrived at Works', 'Under Production',
  'In Transit', 'Ready Awaiting Sailing', 'Under Custom Clearance', 'LC in Process',
  'Costing in Process', 'Order Cancelled'). "ongoing/in progress/currently" =
  current_status NOT IN ('Arrived at Works','Order Cancelled').
- "next/upcoming/soonest/when will X arrive": WHERE date >= CURRENT_DATE ORDER BY date ASC
  (soonest, never past). A plain "when will X arrive" may use ORDER BY eta ASC LIMIT 1.
- "overdue/delayed/late/past due" shipment: sd.eta_final < CURRENT_DATE AND
  id.current_status NOT IN ('Arrived at Works','Order Cancelled'); ORDER BY sd.eta_final ASC;
  days overdue = CURRENT_DATE - sd.eta_final.

IMPORT APPROVAL / DOC FIELDS — sparse, and they have NO "pending" value
- bank_approval, account_approval, docs_status, gin_status and similar import-workflow fields
  are BARELY populated and record only a POSITIVE state: bank_approval / account_approval only
  ever say 'Approved' (~8 rows each), docs_status only 'Received' (2); every other row is
  BLANK/NULL, which means UNRECORDED — NOT "pending". There is no 'Pending'/'Waiting' value.
- So for "waiting for / pending X approval" questions: do NOT filter ILIKE '%pending%' (it
  matches nothing and yields a misleading "no records found"), and do NOT treat blanks as
  pending (they're untracked, not confirmed waiting). Instead report the recorded 'Approved'
  (or 'Received') count and state that the field only tracks that positive state, so the
  pending/waiting set CANNOT be determined from this data.

EXPORTS / LOGISTICS STATUS VOCABULARY (these columns use FIXED values — a plain
ILIKE '%pending%' usually finds NOTHING; map the concept to the real values)
- export_shipments.shipment_status: 'Delivered','Sailing','At QFL','At Port' (parallel
  shipment_stage 'POD','On-Water','QFL','SAPT'). "pending/outstanding/in-progress/not
  delivered / still to ship" shipment = shipment_status <> 'Delivered' (Sailing/At QFL/At
  Port); "on water/sailing" = 'Sailing'; "at port" = 'At Port'; "at QFL/works" = 'At QFL';
  "delivered/completed" = 'Delivered'.
- export_documents.status: 'Done','Pending','In Process','EFS','Non-EFS','Courier Pending',
  'Scan Pending','Under Correction',… Here 'Pending' IS a real value: "pending/waiting
  documentation/docs" = status ILIKE '%pending%' OR status <> 'Done'; "completed docs" =
  status = 'Done'.
- packing_details.overall_status: only 'Pending Packing' or 'In Progress'. "pending/awaiting/
  not packed" = 'Pending Packing'; "being packed/in progress" = 'In Progress'. NOTE
  packing_details.packing_status is FREE-TEXT and inconsistently spelled ('Gate Out'/'Gate
  out'/'Gateout', 'Packed', dates…) — filter/group on overall_status, NOT packing_status
  (lower(btrim()) it if you truly must use it).
- shifting_movements.operational_status / shipment_status / tracking_status: each only
  'Delivered' or NULL. "not delivered/pending movement" = status IS DISTINCT FROM 'Delivered'
  (i.e. NULL) — but NULL here usually means UNREPORTED, so say the progress is unreported
  rather than asserting it is pending.

ACTUAL vs BUDGET / VARIANCE (quoted = budget, actual = actual) — compare on MATCHED rows only
- The quote/actual pairs are SPARSELY populated: quoted_sea_freight/actual_sea_freight
  (export_shipments), quoted_packing_cost/actual_packing_cost (packing_details),
  quoted_freight_rs/actual_freight_rs (shifting_movements). To compare a category, SUM BOTH
  sides over the SAME rows — only those where BOTH are non-null (WHERE quoted IS NOT NULL AND
  actual IS NOT NULL). Summing each side over all rows independently compares DIFFERENT row
  sets and makes the variance meaningless. Include the matched-row count so the basis is clear.
- A category with NO quotes (or no actuals) has NO comparable budget — report it as "no budget
  recorded / no data"; do NOT compare its actuals against 0 or call it over/under budget.

DELAYS / LATE — a delay is an ACTUAL date LATER than its PLANNED/target date (or an item past a
deadline while still not completed), NEVER just "not in a final status". Do NOT count
in-progress / not-delivered / not-done rows as "delayed": those are pipeline states, not delays,
and each table's population differs so such counts are NOT comparable across stages.
- Packing late = actual_rfd_date > target_rfd (only ~490 rows have both; ~379 are late). The
  target_packing_date/actual_packing_date pair is EMPTY — never use it. And overall_status
  (only 'Pending Packing'/'In Progress') can NEVER indicate delay — it matches 100% of rows.
- Import shipment overdue = sd.eta_final < CURRENT_DATE AND id.current_status NOT IN
  ('Arrived at Works','Order Cancelled') (see IMPORT STATUS & TIMING).
- export_shipments and shifting_movements have NO reliable planned-vs-actual date pair, so
  delay is NOT measurable for them — do NOT equate 'not Delivered' with 'delayed'; say delay
  cannot be measured there rather than inventing one.
- When comparing stages ("which stage causes the most delays"), compare ONLY stages where
  delay is genuinely measurable, by count or RATE of truly-late rows, and state which stages
  cannot be measured — never rank by "records not in a final state".

PROJECTED STOCK "once the upcoming import arrives"
- An item can have SEVERAL upcoming imports, and shipment_details has one row per batch — so
  joining shipment_details directly to import_item multiplies rows (batch x line-item), and
  a bare LIMIT 1 drops shipments sharing the same date. Do two safe steps:
    1) per-import qty WITHOUT shipment_details:
       SELECT ii.import_id, SUM(ii.qty) AS import_qty FROM import_item ii
       WHERE ii.item_code = <item> GROUP BY ii.import_id
    2) each upcoming import's earliest ETA:
       SELECT id.import_id, MIN(sd.eta_final) AS eta FROM import_details id
       JOIN shipment_details sd ON sd.import_id = id.import_id
       WHERE sd.eta_final >= CURRENT_DATE
         AND id.current_status NOT IN ('Arrived at Works','Order Cancelled')
       GROUP BY id.import_id
  Join on import_id, take the EARLIEST eta, and SUM import_qty across ALL imports sharing it
  = incoming_qty. projected_stock = current_available + incoming_qty.
- IMPORT UNIT CONVERSION: import_item.qty is expressed in import_item.uom, which is
  FREE-TEXT and usually DIFFERENT from the item's canonical items.uom (e.g. import says
  150 'Ton' but the item is stocked in 'kg'). Before adding incoming import qty to stock
  or consumption quantities (which are in items.uom), CONVERT it. For a kg item:
      CASE
        WHEN lower(btrim(ii.uom)) IN ('ton','tons','t','mt','m.ton','metric ton') THEN ii.qty*1000
        WHEN lower(btrim(ii.uom)) IN ('kg','kgs','kilogram','kilograms') OR ii.uom IS NULL THEN ii.qty
        ELSE NULL  -- unrecognised / incompatible unit: do NOT silently add
      END
  Use the converted value as incoming_qty. If the conversion is NULL (unknown unit, or the
  item is not mass-based like 'No'/'Ltr'/'Pcs'), do NOT add it silently — surface the raw
  qty + its uom and note the unit could not be converted. NEVER add a raw import qty of a
  different unit straight onto a stock quantity.

GRACEFUL DEGRADATION — don't let an OPTIONAL piece zero out the answer
- For a question combining several pieces about ONE item (current stock + incoming import +
  consumption), anchor on the ITEM (always exists) and LEFT JOIN each piece as its own
  aggregated subquery on item_code, each COALESCE(...,0). Never drive (FROM) off the upcoming
  shipment or any optional match — if there's no upcoming import, that returns zero rows and
  looks like "no data" when the truth is "no upcoming import; on current stock you have N
  days". Guard rates: stock_days = projected_stock / NULLIF(daily_consumption, 0) — NULL when
  no usage history (say so). Always return the item's row and state which pieces are missing.

NULLS, RATES & DATES
- Ranking ("top/highest/lowest/largest"): append NULLS LAST, consider WHERE col IS NOT NULL.
  SUM/AVG/MIN/MAX already ignore NULLs.
- Per-day rate / forecast / inventory turnover / days-of-stock: spread the total over the
  CALENDAR span, NOT only active days. Divide by calendar days:
  SUM(measure) / NULLIF((MAX(date_col) - MIN(date_col) + 1), 0), or by a fixed window when
  implied ("last 90 days"->/90). DATA-CURRENCY: tables can lag "today", so don't divide by
  the nominal window length if data ends earlier — bound the divisor to days that have data:
  (LEAST(CURRENT_DATE, MAX(date_col)) - window_start + 1), or just
  (MAX(date_col) - MIN(date_col) + 1) over rows in the window. Then:
      average_daily      = SUM(measure) / calendar_days
      inventory_turnover = (average_daily * 365) / NULLIF(stock_value, 0)
      days_of_stock      = stock_value / NULLIF(average_daily, 0)
  NEVER divide these by COUNT(DISTINCT date_col) (active-only days overstate turnover /
  understate days of stock); use SUM/COUNT(DISTINCT date) ONLY for "average per issuing day".
  NEVER use AVG(measure)/COUNT(days).
- purchases_data has THREE dates: ppc_store = demand/requirement raised; required_d =
  required-by deadline (often future); purchase = actually purchased. Procurement lead time /
  "delay from demand to purchase" = AVG(purchase - ppc_store) (plain average of day-diffs,
  NOT divided by COUNT(DISTINCT date)). NEVER use required_d as the demand date.
- "delayed/late" LOCAL purchase order (a purchases_data row, NOT an import) = purchase >
  required_d (days late = purchase - required_d, only when both dates exist); a purchase with
  no purchase date yet (purchase IS NULL) is still PENDING/outstanding. This is separate from
  the import "overdue shipment" rule above — pick the one matching the supplier's domain.
- store_requisition "behind schedule / late / how many days late" (also "which department is
  behind"): required_date = required-by date; stock_in_date = when stock actually arrived. A
  requisition is late when stock arrived AFTER its required date (stock_in_date > required_date)
  OR it is still unstocked past it (stock_in_date IS NULL AND required_date < CURRENT_DATE).
  days_behind = COALESCE(stock_in_date, CURRENT_DATE) - required_date — measure to the ARRIVAL
  date when stocked, and only to today while still outstanding. NEVER use CURRENT_DATE -
  required_date for an already-stocked row: it counts to today and hugely overstates the delay
  (a requisition stocked 10 days late reads as ~200 days late). "CURRENTLY behind" = still
  outstanding (stock_in_date IS NULL AND required_date < CURRENT_DATE), which is a smaller set
  than "was ever late".

SAFETY STOCK & REORDER LEVEL (ROP) — always PER BRANCH
- ab_items holds per-item, per-BRANCH planning params: branch_name, lead_time_days,
  safety_days, rank. An item normally has ONE ab_items row PER BRANCH, and only some branches
  are covered. Safety stock and reorder level are therefore PER-BRANCH figures, never
  company-wide.
- Formulae (in the item's items.uom; safety_days & lead_time_days are in days):
      branch_daily_usage = branch's average DAILY consumption (see below)
      safety_stock   = branch_daily_usage * safety_days
      reorder_level  = branch_daily_usage * (lead_time_days + safety_days)
- CRITICAL: branch_daily_usage MUST be that branch's OWN usage, NOT company-wide usage.
  Multiplying company-wide usage by one branch's params overstates every branch (it gives
  each branch the whole company's consumption). Compute usage PER BRANCH from issuance
  filtered to that branch, spread over the calendar span (see rates rule):
      SUM(issuance.quantity)/NULLIF(MAX(from_date)-MIN(from_date)+1,0)  GROUP BY branch
  issuance.branch and ab_items.branch_name use the SAME spellings (e.g. 'Qadcast (Pvt) Ltd.',
  'Qadri Brothers (Pvt.) Ltd. (Unit-II)'), so join each ab_items branch to that branch's usage
  ON issuance.branch = ab_items.branch_name. This branch join is SAFE and is the ONE exception
  to the "don't join on text attributes" rule — it holds for BRANCH, never for uom.
- OUTPUT: one row per branch (branch, branch_daily_usage, the params, the computed figure,
  uom). If the item has ONE branch, or every branch yields the SAME value, present a SINGLE
  figure and note it applies to all branches. If branches differ (they usually do — per-branch
  usage differs), show EACH branch's value; NEVER collapse differing branch values into one
  number, and never label a company total as "per branch".
- A branch with no issuance history has NULL branch_daily_usage -> the figure is unknown for
  that branch; say so rather than treating it as 0.
ITEM STOCK-HEALTH STATUS (critical / red flag / reorder / dead stock / healthy) — PER BRANCH
- Every ab_items row (item+branch) gets ONE status from its available stock vs its
  forecast-driven safety/reorder thresholds. The forecast is HISTORICAL ISSUANCE: use the
  branch daily usage (SUM(issuance.quantity)/NULLIF(MAX(from_date)-MIN(from_date)+1,0) GROUP BY
  item_code, branch), NOT rank. Do NOT map "critical" to rank='A' (rank A/B is importance, not
  stock health).
- Build these per item+branch: stock_qty = SUM(stock.stock_qty) — the TOTAL on-hand stock
  quantity, NOT stock.available_qty (available excludes held stock; the status model uses the
  full stock_qty); daily_usage (above); safety_stock = daily_usage*safety_days; reorder_level =
  daily_usage*(lead_time_days+safety_days); in_transit_qty = that item's UPCOMING import qty
  (SUM(import_item.qty) for imports with sd.eta_final>=CURRENT_DATE and current_status NOT IN
  ('Arrived at Works','Order Cancelled'); item-level — imports carry no branch); last_issue =
  MAX(issuance.from_date) for the item+branch.
- Assign status with this CASE (evaluated top-down, first match wins):
    CASE
      WHEN daily_usage IS NULL OR daily_usage = 0 THEN
        CASE WHEN last_issue IS NULL OR last_issue < CURRENT_DATE - INTERVAL '12 months'
             THEN 'Dead Stock (Review Before Action)' ELSE 'Healthy (OK)' END
      WHEN stock_qty < daily_usage*safety_days                    THEN 'Critical (Below Safety Stock)'
      WHEN stock_qty < daily_usage*lead_time_days                 THEN 'Red Flag (Urgent Order Required)'
      WHEN stock_qty < daily_usage*(lead_time_days+safety_days) THEN
        CASE WHEN stock_qty + in_transit_qty < daily_usage*(lead_time_days+safety_days)
             THEN 'Reorder - Shortfall in Transit' ELSE 'Reorder - Covered by Transit' END
      ELSE 'Healthy (OK)'
    END
  Meaning: Critical = below safety stock; Red Flag = won't even last the lead time (stock runs
  out before a fresh order could arrive); Reorder band = below reorder level, split by whether
  incoming imports cover it; Dead Stock = no usage AND no issuance in 12 months; else Healthy.
- "CRITICAL items" specifically = status 'Critical (Below Safety Stock)' (stock_qty <
  safety_stock). "At risk / needs ordering" = Critical + Red Flag + the two Reorder statuses.
  Scope to one branch when a branch is named. Rows with NULL safety_days/lead_time_days can't
  be assessed.
- IF User query have category in it try to write sql query with strict searching of that word in category table

ALIASES
- qcl = Qadcast (Pvt) Ltd.; qbl2 = Qadri Brothers Unit 2; qen = Qadri Engineering (Pvt) Ltd.;
  qe = Qadbros Engineering.

Database schema:
{schema}"""

_SUMMARY_SYSTEM = """You are a helpful supply-chain data assistant. Given the user's
question, a block of exact RESULT FACTS, and a preview of the rows, write a brief,
direct answer in plain English (3-8 sentences max). The full result is already shown
to the user as a table, so do NOT repeat every row — highlight the key findings.

GROUNDING — every number must be exact; do NOT do your own arithmetic:
- State ONLY numbers that appear verbatim in the RESULT FACTS block (or, for an
  individual row's value, in the preview). NEVER add rows together, sum groups, or
  otherwise compute a new total yourself — the FACTS block already gives the exact
  row count, per-group totals ("... summed by ..."), and per-column non-null counts.
  Quote those figures directly.
- For "how many X" about a category, use the exact per-group number from the FACTS,
  not a value you estimated from the preview.
- Quantifiers — "most", "majority", "few", "largely", "many lack X" — are proportion
  claims. Make them ONLY when the per-column non-null counts support them (e.g. do
  NOT say records "lack ETAs" when the ETA count shows most rows have one). A column
  that is mostly populated is NOT "missing".
- Do not generalise about a column's dominant value from the truncated preview; rely
  on the FACTS block. If a number you'd need is not in the FACTS, describe it
  qualitatively rather than guessing.
- If the result is empty, say that no matching records were found."""


# ---------------------------------------------------------------------------
# LangGraph
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    question: str
    history: Any          # {"question": str, "sql": str} of the previous turn | None
    date_range: Any       # (from_iso, to_iso) chosen window | None (either side may be None)
    display: str          # 'text' | 'table' | 'chart' — table/chart skip the summarize LLM
    sql: str
    data: Any            # pandas.DataFrame | None
    error: Optional[str]
    answer: str
    attempts: int


# Heuristic: is the message a follow-up to the previous turn (attach prior context),
# or a self-contained new query? Attach ONLY on a positive follow-up signal, so a
# clearly-new question can never be contaminated by the previous SQL.
_FOLLOWUP_RE = re.compile(
    r"\b(it|its|that|those|these|them|they|this|same|again|instead|also|"
    r"sort|order\s+by|ascending|descending|asc|desc|group\s+by|"
    r"only|just|filter|exclude|remove|narrow|"
    r"what\s+about|how\s+about|and\s+the|top\s+\d+|bottom\s+\d+|first\s+\d+)\b"
    r"|\b(as|in)\s+(a\s+)?(table|chart|graph|plot|pie|bar|line|list|csv)\b",
    re.I,
)


# Display-format words and the filler around them. A message built ONLY from these
# ("show me the table", "as a bar chart", "make it a pie") is a pure format directive
# about the previous result — it carries no data subject of its own.
_FORMAT_WORDS = {
    "table", "chart", "graph", "plot", "pie", "donut", "bar", "line", "list",
    "csv", "excel", "spreadsheet", "histogram", "trend", "download",
    # plural forms so "show tables" / "as bar charts" are also caught
    "tables", "charts", "graphs", "plots", "pies", "donuts", "bars", "lines",
    "lists", "spreadsheets", "histograms", "trends",
}
_FORMAT_FILLER = {
    "show", "me", "us", "the", "a", "an", "as", "in", "into", "to", "of", "it",
    "this", "that", "them", "please", "pls", "can", "you", "could", "would", "give",
    "view", "display", "render", "make", "want", "see", "now", "just", "instead",
    "also", "put", "on", "with", "and", "form", "format", "kindly",
}


def is_pure_format_directive(question: str) -> bool:
    """True when the message is ONLY a display-format request with no data subject
    of its own — e.g. 'show me the table', 'as a bar chart', 'make it a pie'. It
    must contain a format word AND have nothing left after removing format words
    and filler. 'show me table of upcoming shipments' is NOT pure ('upcoming
    shipments' remains), so it stays a NEW query rather than reusing the prior SQL."""
    words = re.findall(r"[a-z0-9]+", (question or "").lower())
    if not words or not any(w in _FORMAT_WORDS for w in words):
        return False
    leftover = [w for w in words if w not in _FORMAT_WORDS and w not in _FORMAT_FILLER]
    return not leftover


def is_followup(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return False
    if is_pure_format_directive(q):  # 'show me the table', 'as a bar chart'
        return True
    if _FOLLOWUP_RE.search(q):      # referential / continuation / format cue
        return True
    return len(q.split()) <= 3      # very short, likely subject-less ("in table", "top 5")


def _generate_sql(state: AgentState) -> AgentState:
    llm = get_llm()
    system = _SQL_SYSTEM.format(schema=get_schema(), max_rows=MAX_ROWS)
    human = ""
    h = state.get("history")
    if h and h.get("sql") and is_followup(state["question"]):
        human += (
            "Recent turn (for follow-ups). The previous question and its SQL are below.\n"
            "If the new message contains its OWN complete question (its own subject or "
            "metric), treat it as NEW and IGNORE the previous SQL — even if it also asks "
            "for a chart/table format. Only REUSE or adapt the previous SQL when the new "
            "message is purely a format or refinement directive with no subject of its "
            "own (e.g. 'show as a table', 'sort by X', 'only the low ones', 'top 5').\n"
            f"Previous question: {h.get('question', '')}\n"
            f"Previous SQL:\n{h.get('sql')}\n\n"
        )
    human += f"Question: {state['question']}"
    dr = state.get("date_range")
    if dr and (dr[0] or dr[1]):
        lo, hi = dr
        if lo and hi:
            clause = f"BETWEEN '{lo}' AND '{hi}' (inclusive)"
        elif lo:
            clause = f">= '{lo}'"
        else:
            clause = f"<= '{hi}'"
        human += (
            "\n\nDATE FILTER — the user chose this time window. Restrict the result to it by "
            f"filtering the table's PRIMARY event-date column {clause}. Use the date column "
            "that matches the data being queried, e.g. issuance.from_date, "
            "purchases_data.purchase, import_details.demand_date, shipment_details.eta_final, "
            "payment_history.payment_ref_date, store_requisition.prepare_date, "
            "exports.sailing_date, packing_details.actual_packing_date, "
            "shifting_movements.execution_date. If the queried table genuinely has no date "
            "column (e.g. current stock snapshot, items master), ignore this filter."
        )
    if state.get("error"):
        human += (
            f"\n\nYour previous query failed:\n{state['sql']}\n\n"
            f"PostgreSQL error:\n{state['error']}\n\nFix it and return corrected SQL."
        )
    raw = llm.invoke([("system", system), ("human", human)]).content
    sql = add_limit(clean_sql(raw))
    attempt = state.get("attempts", 0) + 1
    print(f"\n[chatbot] Q: {state['question']}", flush=True)
    print(f"[chatbot] SQL (attempt {attempt}):\n{sql}", flush=True)
    return {"sql": sql, "attempts": attempt}


def _execute_sql(state: AgentState) -> AgentState:
    sql = state.get("sql", "")
    if not is_safe_select(sql):
        return {"data": None, "error": "Only read-only SELECT queries are allowed."}
    try:
        with get_engine().connect() as conn:
            df = pd.read_sql_query(text(sql), conn)
        df = dedupe_columns(df)
        print(f"[chatbot] rows returned: {len(df)}", flush=True)
        return {"data": df, "error": None}
    except Exception as exc:  # surfaced back to the model for a retry
        err = str(exc).strip()
        print(f"[chatbot] SQL error: {err}", flush=True)
        return {"data": None, "error": err}


def _route_after_execute(state: AgentState) -> str:
    if state.get("error") and state.get("attempts", 0) < MAX_ATTEMPTS:
        return "retry"
    return "summarize"


# Columns that are identifiers, not measures — never sum/average them.
_ID_COL_RE = re.compile(r"(^|_)(id|no|code|ref|number)$", re.I)


def _fmt_num(v):
    """Format a number as a clean int when whole, else 2 dp; NaN -> None."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    if pd.isna(f):
        return None
    return int(f) if f == int(f) else round(f, 2)


def _result_facts(df: pd.DataFrame, max_groups: int = 20) -> str:
    """Deterministic ground truth handed to the summarizer so it never has to
    (mis)compute a total itself: exact row count, per-column non-null coverage,
    numeric column sums/min/max/mean, and — for a single measure grouped by a
    category — the exact per-group totals (e.g. packing_jobs by overall_status).
    Computed by pandas, not the LLM, so the numbers are always correct."""
    try:
        n = len(df)
        lines = [f"total rows: {n}"]

        num_cols = df.select_dtypes(include="number").columns.tolist()
        measure_cols = [c for c in num_cols if not _ID_COL_RE.search(str(c))]
        obj_cols = [c for c in df.columns if c not in num_cols]

        # per-column non-null counts — grounds every "most/few/lack X" claim.
        cov = "; ".join(f"{c}: {int(df[c].notna().sum())}/{n}" for c in df.columns)
        lines.append(f"non-null count per column: {cov}")

        # numeric measure aggregates (identifiers excluded).
        for c in measure_cols:
            s = df[c]
            if s.notna().any():
                lines.append(
                    f"column '{c}': sum={_fmt_num(s.sum())}, min={_fmt_num(s.min())}, "
                    f"max={_fmt_num(s.max())}, mean={_fmt_num(s.mean())}"
                )

        # exactly one measure + a grouping category -> exact per-group totals.
        if len(measure_cols) == 1 and obj_cols and n > 1:
            gcol, mcol = obj_cols[0], measure_cols[0]
            if df[gcol].nunique(dropna=False) < n:      # only if it truly groups
                grp = (df.groupby(gcol, dropna=False)[mcol]
                         .sum().sort_values(ascending=False))
                shown = "; ".join(
                    f"{'NULL' if pd.isna(k) else k}={_fmt_num(v)}"
                    for k, v in grp.head(max_groups).items()
                )
                extra = "" if len(grp) <= max_groups else f" (+{len(grp) - max_groups} more)"
                lines.append(f"'{mcol}' summed by '{gcol}': {shown}{extra}")

        return "\n".join(lines)
    except Exception:                                    # never break summarize
        return f"total rows: {len(df)}"


def _summarize(state: AgentState) -> AgentState:
    if state.get("error"):
        return {
            "answer": "Sorry — I couldn't answer that from the database "
                      f"(the query kept failing). Last error: {state['error']}"
        }
    df: pd.DataFrame = state["data"]
    n = len(df)
    if n == 0:
        return {"answer": "No matching records were found."}
    # Table/chart displays show the data itself, so skip the summarize LLM call and
    # return a fast, exact one-line caption — this removes a full model round-trip
    # (~2s) from every "show me ... as a table/chart" question.
    disp = state.get("display", "text")
    if disp in ("table", "chart"):
        capped = (f" (showing the first {MAX_ROWS:,}; the full result is larger)"
                  if n >= MAX_ROWS else "")
        noun = "record" if n == 1 else "records"
        if disp == "chart":
            return {"answer": f"Charted {n:,} {noun}{capped}."}
        return {"answer": f"Here {'is' if n == 1 else 'are'} {n:,} matching {noun}{capped}."}
    facts = _result_facts(df)
    preview = df.head(20).to_string(index=False)
    # n == MAX_ROWS means the query almost certainly hit the LIMIT cap, so these
    # rows are a partial slice — the totals/coverage below describe ONLY them, not
    # the full result. Tell the summarizer so it caveats instead of implying it's
    # the complete picture.
    truncated_note = ""
    if n >= MAX_ROWS:
        truncated_note = (
            f"\n\nIMPORTANT — the result was CAPPED at {MAX_ROWS} rows (the query's "
            f"LIMIT). The full result is LARGER. Every count/sum/coverage above covers "
            f"only these {MAX_ROWS} shown rows, so do NOT present them as complete "
            f"totals — say e.g. 'at least {MAX_ROWS}' / 'among the first {MAX_ROWS} "
            f"shown' and note the full set is larger. Avoid ranking claims (top/leading) "
            f"since the shown rows are only a partial, ordered slice."
        )
    llm = get_llm()
    human = (
        f"Question: {state['question']}\n\n"
        f"RESULT FACTS (exact, computed by the database — quote these, do not recompute):\n"
        f"{facts}{truncated_note}\n\n"
        f"Row preview (first 20 of {n}):\n{preview}"
    )
    answer = llm.invoke([("system", _SUMMARY_SYSTEM), ("human", human)]).content
    return {"answer": answer}


@lru_cache(maxsize=1)
def get_graph():
    from langgraph.graph import StateGraph, START, END
    g = StateGraph(AgentState)
    g.add_node("generate_sql", _generate_sql)
    g.add_node("execute_sql", _execute_sql)
    g.add_node("summarize", _summarize)
    g.add_edge(START, "generate_sql")
    g.add_edge("generate_sql", "execute_sql")
    g.add_conditional_edges(
        "execute_sql", _route_after_execute,
        {"retry": "generate_sql", "summarize": "summarize"},
    )
    g.add_edge("summarize", END)
    return g.compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def answer_question(question: str, history: Optional[dict] = None,
                    date_range: Optional[tuple] = None) -> dict:
    """Run the agent and return {sql, dataframe, answer, error, display, chart_type}.

    `history` is the previous turn's {"question", "sql"} (or None) so follow-ups
    like "show as a table" / "sort by X" can be interpreted in context.
    `date_range` is an optional (from_iso, to_iso) window (either side may be None)
    to restrict a time-series query to — see detect_date_range_need/parse_date_range."""
    # Decide display intent up front so the graph's summarize step can skip its LLM
    # call for table/chart results (the data is shown directly).
    display, chart_type = detect_display(question)
    final: AgentState = get_graph().invoke(
        {"question": question, "history": history, "date_range": date_range,
         "display": display, "attempts": 0, "error": None}
    )
    df = final.get("data")
    # No data (error/empty) -> just describe, never a table/chart.
    if final.get("error") or not isinstance(df, pd.DataFrame) or df.empty:
        display, chart_type = "text", None
    print(f"[chatbot] answer: {final.get('answer', '')}", flush=True)
    print(f"[chatbot] display: {display}"
          + (f" ({chart_type})" if chart_type else "") + "\n", flush=True)
    return {
        "sql": final.get("sql"),
        "dataframe": df if isinstance(df, pd.DataFrame) else None,
        "answer": final.get("answer", ""),
        "error": final.get("error"),
        "display": display,
        "chart_type": chart_type,
    }


# ---------------------------------------------------------------------------
# Date-range clarification — for a time-series question with no timeframe of its
# own, the chatbot first asks "between which dates?" and then injects the chosen
# window into SQL generation (see answer_question(date_range=...)).
# ---------------------------------------------------------------------------

# Pre-gate 1: the question ALREADY states a timeframe -> never ask.
_HAS_TIMEFRAME_RE = re.compile(
    r"\b(today|yesterday|now|current|currently|latest|recent|ongoing|upcoming|"
    r"overdue|pending|last|past|previous|this|next|since|until|till|ago|"
    r"ytd|mtd|q[1-4]|quarter|"
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b"
    r"|\d{4}|\d{1,2}[/-]\d{1,2}",
    re.I,
)
# Pre-gate 2: the question is plausibly about dated (time-series) data.
_DATE_SUBJECT_RE = re.compile(
    r"\b(issu\w*|consum\w*|usage|used|purchas\w*|bought|order\w*|"
    r"import\w*|shipment\w*|ship\w*|payment\w*|paid|requisition\w*|demand\w*|"
    r"export\w*|packing|movement\w*|shifting|deliver\w*|transaction\w*|"
    r"history|trend|activity|records?|data)\b",
    re.I,
)

_DATE_INTENT_SYSTEM = """You gate a supply-chain data assistant. Decide whether it should FIRST
ask the user for a DATE RANGE before querying. Answer needs_range=true ONLY when BOTH hold:
1) The data is time-series — individual dated events: issuances/consumption, local purchases,
   imports, shipments, payments, requisitions, exports, packing, or movements (tables with a
   date per row).
2) The question gives NO timeframe of its own and is a broad "show / list / give me the data /
   history" style request over many rows, where a window is genuinely useful.
Answer needs_range=false for: current-snapshot questions (current/available stock, item specs,
"latest" X — these have no per-row date); anything that already names a timeframe; single-fact
lookups ("who supplied our last order of resin"); ongoing/upcoming/overdue/pending STATUS
questions (they key off CURRENT_DATE, not a user window); and rankings/aggregates that read
naturally over all history unless the user clearly wants a period.
When true, propose a sensible default window ending today (default to the last 6 months).
Return ONLY minified JSON:
{"needs_range": true/false, "default_from": "YYYY-MM-DD", "default_to": "YYYY-MM-DD"}"""


def detect_date_range_need(question: str) -> dict:
    """Return {needs_range, default_from, default_to}. Cheap regex pre-gates first
    (already has a timeframe, or not a dated subject -> skip the LLM); only then a
    small LLM confirmation so we don't nag on snapshot/status questions."""
    q = (question or "").strip()
    off = {"needs_range": False, "default_from": "", "default_to": ""}
    if not q or _HAS_TIMEFRAME_RE.search(q) or not _DATE_SUBJECT_RE.search(q):
        return off
    today = date.today().isoformat()
    raw = get_llm().invoke(
        [("system", _DATE_INTENT_SYSTEM), ("human", f"Today: {today}\nQuestion: {q}")]
    ).content
    try:
        s = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.I).strip()
        d = json.loads(s)
        return {"needs_range": bool(d.get("needs_range")),
                "default_from": (d.get("default_from") or "").strip(),
                "default_to": (d.get("default_to") or "").strip()}
    except Exception:
        return off


_RANGE_PARSE_SYSTEM = """The user was asked "between which dates?" for a data query. Convert their
reply into a concrete date range, using today's date to resolve relative phrases ("last 3
months", "this year", "since March", "Jan to June 2025", "2026-01-01 to 2026-06-30").
Rules: all=true if they want everything / all time / no limit / skip. If only a start is given,
set to=today. If only an end is given, leave from empty. If the reply can't be parsed as dates,
all=true. Return ONLY minified JSON:
{"all": true/false, "from": "YYYY-MM-DD", "to": "YYYY-MM-DD"}  (from/to empty when not applicable)"""


def parse_date_range(reply: str, today: Optional[str] = None):
    """Map the user's reply to a (from_iso, to_iso) tuple, or None for 'no date
    filter' (all time / unparseable). Either side of the tuple may be None."""
    r = (reply or "").strip()
    if not r:
        return None
    today = today or date.today().isoformat()
    raw = get_llm().invoke(
        [("system", _RANGE_PARSE_SYSTEM), ("human", f"Today: {today}\nReply: {r}")]
    ).content
    try:
        s = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.I).strip()
        d = json.loads(s)
        if d.get("all"):
            return None
        lo = (d.get("from") or "").strip() or None
        hi = (d.get("to") or "").strip() or None
        return (lo, hi) if (lo or hi) else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Item disambiguation — used by the chatbot page so that "details of <item>"
# questions first confirm WHICH specific item (same name, different specs).
# ---------------------------------------------------------------------------

ITEM_COLS = ["item_code", "item", "group_name", "material_standard",
             "uom", "item_category", "specs"]


def find_item_candidates(keyword: str, limit: int = 1000) -> pd.DataFrame:
    """Items where EVERY word of the keyword appears somewhere in the combined
    descriptive text (item + group_name + material_standard + item_category +
    specs) — so multi-word names split across item/specs still match (e.g.
    'Hard Coke Anode Butt' = item 'Hard Coke' + specs 'Anode Butt'). A bare
    item_code also matches directly.

    The cap is high (1000, was 25) so a BROAD keyword like 'ball bearing' returns
    all its matches — the chatbot page shows them all as a table rather than a
    truncated pick-list (see MANY_ITEMS in pages/chatbot.py)."""
    kw = (keyword or "").strip()
    tokens = [t for t in re.split(r"\s+", kw) if t]
    if not tokens:
        return pd.DataFrame(columns=ITEM_COLS)
    blob = ("coalesce(item,'')||' '||coalesce(group_name,'')||' '||"
            "coalesce(material_standard,'')||' '||coalesce(item_category,'')||' '||"
            "coalesce(specs,'')")
    conds, params = [], {"lim": limit, "kwfull": f"%{kw}%"}
    for i, tok in enumerate(tokens):
        conds.append(f"{blob} ILIKE :t{i}")
        params[f"t{i}"] = f"%{tok}%"
    sql = text(f"""
        SELECT {", ".join(ITEM_COLS)}
        FROM items
        WHERE ({" AND ".join(conds)}) OR item_code ILIKE :kwfull
        ORDER BY item NULLS LAST, specs NULLS LAST
        LIMIT :lim
    """)
    with get_engine().connect() as conn:
        return pd.read_sql_query(sql, conn, params=params)


# Pre-gate: run the intent LLM only when the message looks item-focused (a detail
# request OR a metric about an item). Broader than detail-only, so single-item
# analytic questions ("stock days of resin") are caught too.
_ITEM_FOCUS_HINT = re.compile(
    r"\b(detail|details|spec|specs|specification|info|information|describe|about|"
    r"what is|tell me about|stock|available|usage|consumption|issued|issuance|"
    r"reorder|forecast|cover|price|cost|lead time|incoming|arriv\w*)\b", re.I,
)

_INTENT_SYSTEM = """Classify a message to a supply-chain data assistant. Decide if it is
FOCUSED ON ONE SPECIFIC inventory item — either asking for its details/specs OR asking a
metric about it (its stock, stock-days, usage, price, forecast, incoming import, etc.).
Set is_item_detail=true when the user refers to a SINGLE product/material by name
(singular phrasing like "resin", "the tap handle", "silica sand"). Set it false ONLY when
they clearly mean MANY/ALL items, a whole category/group, cross-item rankings ("top
items", "which items"), or a supplier/branch aggregate. When unsure but the user names a
single product in the singular, PREFER true. When true, extract the core product keyword.
Return ONLY minified JSON: {"is_item_detail": true/false, "keyword": "<product or empty>"}."""


def extract_item_query(question: str) -> dict:
    """Return {is_item_detail, keyword}. `is_item_detail` now means "focused on one
    specific item" (a detail OR a metric about it). Only calls the LLM when the
    message looks item-focused (see _ITEM_FOCUS_HINT)."""
    if not _ITEM_FOCUS_HINT.search(question or ""):
        return {"is_item_detail": False, "keyword": ""}
    raw = get_llm().invoke(
        [("system", _INTENT_SYSTEM), ("human", question or "")]
    ).content
    try:
        s = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.I).strip()
        d = json.loads(s)
        return {"is_item_detail": bool(d.get("is_item_detail")),
                "keyword": (d.get("keyword") or "").strip()}
    except Exception:
        return {"is_item_detail": False, "keyword": ""}


def _dedupe(seq: list) -> list:
    seen = set()
    return [x for x in seq if not (x in seen or seen.add(x))]


_PICK_SYSTEM = """The user was shown a numbered list of candidate items and asked which
they meant. They may choose ONE or SEVERAL. Given their reply and the candidates, return
the exact item_code(s) they chose as a comma-separated list (e.g. "1004-60, 1002-0").
Return "ALL" if they want every candidate, or "NONE" if the reply matches none."""


def resolve_selections(reply: str, candidates: pd.DataFrame) -> list:
    """Map the user's reply to ONE OR MORE item_codes from the candidate list."""
    if candidates is None or candidates.empty:
        return []
    codes = candidates["item_code"].astype(str).tolist()
    r = (reply or "").strip()
    rl = r.lower()

    if re.search(r"\b(all|every|everything|each)\b", rl):
        return codes
    if re.search(r"\bboth\b", rl) and len(codes) == 2:
        return codes
    typed = [c for c in codes if c.lower() in rl]          # one or more codes typed
    if typed:
        return _dedupe(typed)
    nums = re.findall(r"\d{1,3}", r)                        # "1 and 3", "1,3", "2 & 4"
    picked = [codes[int(n) - 1] for n in nums if 1 <= int(n) <= len(codes)]
    if picked:
        return _dedupe(picked)
    if len(codes) == 1 and re.search(                      # "yes" to the single match
            r"\b(yes|yeah|yep|ok|okay|sure|that|this|correct|right|detail)\b", rl):
        return codes

    listing = "\n".join(                                   # LLM fallback (may return many)
        f"{i + 1}. item_code={row.item_code} | {row.item} | specs={row.specs}"
        for i, row in candidates.reset_index(drop=True).iterrows()
    )
    out = get_llm().invoke(
        [("system", _PICK_SYSTEM),
         ("human", f"Candidates:\n{listing}\n\nReply: {r}")]
    ).content.strip()
    if out.upper().startswith("NONE"):
        return []
    if out.upper().startswith("ALL"):
        return codes
    return [c for c in (x.strip() for x in out.split(",")) if c in codes]


def answer_item_details(item_codes, original_question: str = "",
                        history: Optional[dict] = None) -> dict:
    """Run the normal pipeline pinned to one OR MORE resolved item_codes."""
    codes = [item_codes] if isinstance(item_codes, str) else list(item_codes)
    q = (original_question or "show all details").strip()
    if len(codes) == 1:
        q += f"  (specifically the item with item_code = '{codes[0]}')"
    else:
        joined = ", ".join(f"'{c}'" for c in codes)
        q += (f"  (specifically the items with item_code IN ({joined}); "
              f"show each item separately, do not merge them)")
    return answer_question(q, history=history)
