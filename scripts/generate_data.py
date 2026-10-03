"""ATLAS data generator, step 1: build the database from the schema file
and load the fixed reference tables (products, customers).

Rules: docs/DATA_GENERATION_RULES.md (v0.2). All data is synthetic.
"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "atlas.db"
SCHEMA_PATH = ROOT / "sql" / "01_schema.sql"

PRODUCTS = [
    ("P01", "Industrial Cutting Fluid", "20L container"),
    ("P02", "Abrasive Disc Pack", "box of 50"),
    ("P03", "Protective Glove Set", "box of 100 pairs"),
]


def build_customers():
    """20 fictional customers: Thailand 7, Vietnam 7, Indonesia 6."""
    groups = [("TH", "Thailand", 7), ("VN", "Vietnam", 7), ("ID", "Indonesia", 6)]
    rows = []
    n = 0
    for code, market, count in groups:
        for i in range(1, count + 1):
            n += 1
            rows.append((f"C{n:02d}", f"Customer {code}-{i:02d}", market))
    return rows


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())

    conn.executemany("INSERT INTO products VALUES (?, ?, ?)", PRODUCTS)
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?)", build_customers())
    conn.commit()

    for table in ("products", "customers", "sales", "monthly_targets"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count} rows")

    conn.close()


if __name__ == "__main__":
    main()
