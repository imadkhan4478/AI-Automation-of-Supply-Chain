"""
One-off schema discovery tool.

Usage:
    python inspect_schema.py <table_name> [<table_name> ...]

For each table (assumed schema `public`), prints:
  - columns with their SQL types
  - the first 5 rows

Uses the same engine as the real app (backend.db_connection.get_engine),
so it reads from whatever database is configured in .env.
"""

import sys

import pandas as pd
from sqlalchemy import text

from backend.db_connection import get_engine


def inspect_table(engine, table, schema="public"):
    print(f"\n{'=' * 70}")
    print(f"TABLE: {schema}.{table}")
    print("=" * 70)

    cols = pd.read_sql(
        text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table
            ORDER BY ordinal_position
        """),
        engine,
        params={"schema": schema, "table": table},
    )

    if cols.empty:
        print(f"(no columns found — does {schema}.{table} exist?)")
        return

    print("\n-- columns --")
    print(cols.to_string(index=False))

    sample = pd.read_sql(
        text(f'SELECT * FROM "{schema}"."{table}" LIMIT 5'),
        engine,
    )
    print("\n-- sample rows --")
    if sample.empty:
        print("(table has no rows)")
    else:
        print(sample.to_string(index=False))


def main():
    tables = sys.argv[1:]
    if not tables:
        print("Usage: python inspect_schema.py <table_name> [<table_name> ...]")
        sys.exit(1)

    engine = get_engine()
    for table in tables:
        inspect_table(engine, table)


if __name__ == "__main__":
    main()
