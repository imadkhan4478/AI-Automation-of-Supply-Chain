import psycopg2, pandas as pd
from sqlalchemy import create_engine

engine = create_engine("postgresql+psycopg2://postgres:2023451@localhost:5432/supply_chain")

for tbl in ["purchases_data", "import_details", "issuance", "exports"]:
    print("=" * 60)
    print(f"TABLE: {tbl}")
    cols = pd.read_sql(f"""SELECT column_name, data_type FROM information_schema.columns
                           WHERE table_schema='public' AND table_name='{tbl}'
                           ORDER BY ordinal_position;""", engine)
    print(cols.to_string(index=False))
    print(f"\n--- 3 sample rows of {tbl} ---")
    print(pd.read_sql(f"SELECT * FROM public.{tbl} LIMIT 3;", engine).to_string(index=False))
    print()