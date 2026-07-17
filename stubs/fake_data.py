"""
Fake data for building the frontend before the real backend is ready.

Every function here mirrors the SHAPE of what the real backend/ modules
will eventually return (a dict of KPIs, or a pandas DataFrame). When the
real database/analytics modules are ready, backend/ will call them instead
and these stubs are simply no longer used. The page code never changes.
"""

import random
from datetime import date, timedelta

import pandas as pd

# Keep the fake data stable across reruns so charts don't jump around.
random.seed(42)

_BRANCHES = ["Lahore", "Karachi", "Faisalabad", "Multan"]
_SUPPLIERS = ["Alpha Traders", "Beta Metals", "Gamma Supply Co", "Delta Industrial", "Epsilon Corp"]
_ITEMS = ["Tap Handle 1/2\"", "Thread Gauge", "Bolt Tensioner", "Plain Washer M16", "Three Jaws Chuck"]
_CUSTOMERS = ["Bestway Cement", "Maple Leaf Cement", "Fauji Cement", "DG Khan Cement"]


def _recent_dates(n):
    today = date.today()
    return [today - timedelta(days=random.randint(0, 120)) for _ in range(n)]


# ----------------------------------------------------------------------
# DASHBOARD
# ----------------------------------------------------------------------
def get_dashboard_kpis():
    """Top-level KPI numbers for the management overview."""
    return {
        "total_purchase_orders": 1284,
        "pending_orders": 176,
        "delayed_orders": 42,
        "purchase_value_pkr": 84_500_000,
        "stock_items_at_risk": 37,
        "on_time_rate": 0.86,
    }


def get_purchase_trend():
    """Monthly purchase value, for the dashboard trend chart."""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    values = [12.1, 13.8, 11.4, 15.2, 14.0, 17.9]  # PKR millions
    return pd.DataFrame({"month": months, "purchase_value_m": values})


def get_alerts():
    """Exception / attention panel for the dashboard."""
    return [
        {"level": "high", "message": "3 suppliers chronically late this quarter"},
        {"level": "high", "message": "5 items below reorder point"},
        {"level": "medium", "message": "12 purchase orders pending over 30 days"},
        {"level": "low", "message": "2 shipments awaiting customs clearance"},
    ]


# ----------------------------------------------------------------------
# PURCHASES
# ----------------------------------------------------------------------
def get_purchases(status="All", supplier="All"):
    n = 40
    df = pd.DataFrame({
        "ref_no": [f"PR-{1000 + i}" for i in range(n)],
        "supplier": [random.choice(_SUPPLIERS) for _ in range(n)],
        "item": [random.choice(_ITEMS) for _ in range(n)],
        "branch": [random.choice(_BRANCHES) for _ in range(n)],
        "quantity": [random.randint(10, 500) for _ in range(n)],
        "amount_pkr": [random.randint(50_000, 2_000_000) for _ in range(n)],
        "required_date": _recent_dates(n),
        "status": [random.choice(["Pending", "Completed", "Delayed"]) for _ in range(n)],
    })
    if status != "All":
        df = df[df["status"] == status]
    if supplier != "All":
        df = df[df["supplier"] == supplier]
    return df.reset_index(drop=True)


def get_supplier_list():
    return ["All"] + _SUPPLIERS


# ----------------------------------------------------------------------
# INVENTORY (STORES)
# ----------------------------------------------------------------------
def get_stock(status="All"):
    n = 35
    df = pd.DataFrame({
        "item_code": [f"{1000 + i}-60" for i in range(n)],
        "item": [random.choice(_ITEMS) for _ in range(n)],
        "branch": [random.choice(_BRANCHES) for _ in range(n)],
        "stock_qty": [random.randint(0, 800) for _ in range(n)],
        "available_qty": [random.randint(0, 800) for _ in range(n)],
        "reorder_level": [random.choice([50, 100, 150]) for _ in range(n)],
    })
    df["stock_status"] = df.apply(
        lambda r: "Below reorder" if r["available_qty"] < r["reorder_level"] else "OK", axis=1
    )
    if status != "All":
        df = df[df["stock_status"] == status]
    return df.reset_index(drop=True)


# ----------------------------------------------------------------------
# IMPORTS
# ----------------------------------------------------------------------
def get_imports(status="All"):
    n = 25
    df = pd.DataFrame({
        "import_ref": [f"IMP-{2000 + i}" for i in range(n)],
        "customer": [random.choice(_CUSTOMERS) for _ in range(n)],
        "supplier": [random.choice(_SUPPLIERS) for _ in range(n)],
        "total_value_pkr": [random.randint(500_000, 20_000_000) for _ in range(n)],
        "eta_final": _recent_dates(n),
        "current_status": [random.choice(["In Transit", "Cleared", "Pending Clearance"]) for _ in range(n)],
    })
    if status != "All":
        df = df[df["current_status"] == status]
    return df.reset_index(drop=True)


# ----------------------------------------------------------------------
# LOGISTICS
# ----------------------------------------------------------------------
def get_logistics(kind="Export"):
    n = 20
    df = pd.DataFrame({
        "exp_no": [f"EXP-{3000 + i}" for i in range(n)],
        "customer": [random.choice(_CUSTOMERS) for _ in range(n)],
        "pod": [random.choice(["Jebel Ali", "Hamburg", "Shanghai", "Dubai"]) for _ in range(n)],
        "gross_weight_kgs": [random.randint(500, 25_000) for _ in range(n)],
        "sailing_date": _recent_dates(n),
        "shipment_status": [random.choice(["Booked", "Sailed", "Delivered"]) for _ in range(n)],
    })
    return df.reset_index(drop=True)


# ----------------------------------------------------------------------
# ASSISTANT (fake canned reply)
# ----------------------------------------------------------------------
def ask_assistant(question):
    """Placeholder — the real assistant module will interpret the question."""
    return {
        "understood": "delayed purchase orders, last 90 days",
        "answer": "There are 42 delayed purchase orders in the last 90 days. "
                  "The supplier with the most delays is Beta Metals (11 orders).",
        "table": get_purchases(status="Delayed"),
    }


# ======================================================================
#  EXECUTIVE / ENRICHED DATA (added for the enterprise dashboard)
# ======================================================================
def get_dashboard_kpis_rich():
    """KPIs with trend direction for executive cards."""
    return {
        "purchase_value":   {"value": 84_500_000, "delta": "8% vs last month", "direction": "up", "good_when": "up"},
        "pending_orders":   {"value": 176, "delta": "5% vs last month", "direction": "down", "good_when": "down"},
        "delayed_orders":   {"value": 42, "delta": "12% vs last month", "direction": "up", "good_when": "down"},
        "on_time_rate":     {"value": "86%", "delta": "3% vs last month", "direction": "up", "good_when": "up"},
        "items_at_risk":    {"value": 37, "delta": "9 more than last month", "direction": "up", "good_when": "down"},
        "open_imports":     {"value": 14, "delta": "steady", "direction": None, "good_when": "down"},
    }


def get_health():
    """Overall supply-chain health summary for the banner."""
    return {"level": "watch", "message": "Supply chain stable — 3 issues need attention"}


def get_supplier_performance():
    """On-time % per supplier, for a ranked bar with a target line."""
    return pd.DataFrame({
        "supplier": _SUPPLIERS,
        "on_time_pct": [92, 78, 64, 88, 71],
    })


def get_status_split(kind="purchases"):
    """Composition for a donut chart."""
    if kind == "purchases":
        return (["Completed", "Pending", "Delayed"], [62, 26, 12])
    if kind == "imports":
        return (["Cleared", "In Transit", "Pending Clearance"], [9, 11, 5])
    return (["OK", "Below reorder"], [63, 37])


def get_aging():
    """Aging buckets for pending purchase orders."""
    return pd.DataFrame({
        "bucket": ["0-30 days", "31-60 days", "61-90 days", "90+ days"],
        "orders": [98, 44, 21, 13],
    })
