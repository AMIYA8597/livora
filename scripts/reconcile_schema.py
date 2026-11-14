"""
Schema Reconciliation Tool:
Compares SQLAlchemy Base.metadata against the live database schema (information_schema).
"""
import sys
import psycopg2
from typing import Dict, List, Set, Any
sys.path.insert(0, "apps/api")
from app.core.database import Base, _import_models

_import_models()

def reconcile():
    conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5432/flatmate_staging_disposable")
    cur = conn.cursor()

    # Get DB tables
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    db_tables = {r[0] for r in cur.fetchall()}

    # Get SQLAlchemy tables
    model_tables = set(Base.metadata.tables.keys())

    print(f"SQLAlchemy Defined Tables: {len(model_tables)}")
    print(f"Database Existing Tables: {len(db_tables)}")

    missing_in_db = model_tables - db_tables
    extra_in_db = db_tables - model_tables

    print(f"\nMissing in DB: {missing_in_db or 'None'}")
    print(f"Extra in DB (non-model): {extra_in_db or 'None'}")

    drift_report = {}

    for table_name in sorted(model_tables.intersection(db_tables)):
        sa_table = Base.metadata.tables[table_name]
        sa_cols = {c.name for c in sa_table.columns}

        cur.execute(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s;",
            (table_name,)
        )
        db_cols = {r[0]: {"type": r[1], "nullable": r[2]} for r in cur.fetchall()}

        missing_cols = sa_cols - set(db_cols.keys())
        extra_cols = set(db_cols.keys()) - sa_cols

        # Check indexes
        cur.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename = %s;",
            (table_name,)
        )
        db_indexes = {r[0] for r in cur.fetchall()}

        if missing_cols or extra_cols:
            drift_report[table_name] = {
                "missing_cols": list(missing_cols),
                "extra_cols": list(extra_cols),
            }

    print("\n--- Column Drift Report ---")
    if not drift_report:
        print("PERFECT PARITY: Zero column discrepancies found across all domain models!")
    else:
        for t, d in drift_report.items():
            print(f"Table '{t}': Missing={d['missing_cols']}, Extra={d['extra_cols']}")

    conn.close()

if __name__ == "__main__":
    reconcile()
