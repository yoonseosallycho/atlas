"""ATLAS home screen (first working increment): total revenue from atlas.db.

The SQL lives in sql/03_total_revenue.sql. This file only runs it and shows
the result. The database is opened read-only, so the app cannot change data.
All data is synthetic.
"""
import sqlite3
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "atlas.db"
SQL_PATH = ROOT / "sql" / "03_total_revenue.sql"


def run_query(sql_path):
    """Run a one-row SQL file against atlas.db and return (sql text, dict)."""
    sql = sql_path.read_text()
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
    try:
        cursor = conn.execute(sql)
        columns = [col[0] for col in cursor.description]
        row = cursor.fetchone()
    finally:
        conn.close()
    return sql, dict(zip(columns, row))


st.set_page_config(page_title="ATLAS", layout="wide")

st.title("ATLAS")
st.caption("Commercial intelligence and strategy for multi-market B2B businesses (MVP)")

st.info(
    "Synthetic data only. Every figure comes from independently generated, "
    "fictional data for a made-up supplier (20 customers, 3 markets). "
    "Nothing here describes a real company."
)

if not DB_PATH.exists():
    st.error(
        "atlas.db was not found. Create it by running "
        "`python3 scripts/generate_data.py` from the project folder."
    )
    st.stop()

sql_text, result = run_query(SQL_PATH)

col_revenue, col_lines, col_period = st.columns(3)
col_revenue.metric("Total revenue (USD, synthetic)", f"${result['total_revenue_usd']:,.2f}")
col_lines.metric("Sales lines", f"{result['sales_lines']:,}")
col_period.metric(
    "Data period",
    f"{result['first_sale_date'][:7]} to {result['last_sale_date'][:7]}",
)

st.caption(
    f"Sales dates run from {result['first_sale_date']} to {result['last_sale_date']} "
    f"({result['months_with_sales']} calendar months with sales)."
)

st.markdown(
    "**How this is calculated.** Revenue of one sales line = quantity x net unit "
    "price (USD per unit of sale). The total adds up every sales line in the "
    "database: all markets, all products, the whole period. No filters yet."
)

with st.expander("SQL used for this screen (sql/03_total_revenue.sql)"):
    st.code(sql_text, language="sql")
