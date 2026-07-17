"""Quick check of logistics/export table + view columns."""
import pandas as pd
from sqlalchemy import text
from backend.db_connection import get_engine

engine = get_engine()

# Candidate logistics relations — edit this list if the real names differ.
candidates = [
    "exports", "shipment_details", "export_details",
    "v_shipment_metrics", "v_packing_metrics",
    "v_shifting_metrics", "v_documentation_completion",
]

for rel in candidates:
    print("=" * 60)
    print(rel)
    print("=" * 60)
    try:
        df = pd.read_sql(text(f'SELECT * FROM public."{rel}" LIMIT 3'), engine)
        print("COLUMNS:", list(df.columns))
        print(df.to_string(index=False))
    except Exception as e:
        print(f"(skip — {e})")
    print()

    print(pd.read_sql(text(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema='public' ORDER BY table_name"), engine).to_string())