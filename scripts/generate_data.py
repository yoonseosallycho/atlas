"""ATLAS data generator, step 3: build the database from the schema file,
load the fixed reference tables (products, customers), create the
customer profiles, and plan how many sales lines each market-month gets.

Rules: docs/DATA_GENERATION_RULES.md (v0.2). All data is synthetic.
"""
import random
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "atlas.db"
SCHEMA_PATH = ROOT / "sql" / "01_schema.sql"

SEED = 20240101  # fixed seed (rules section 3)

PRODUCTS = [
    ("P01", "Industrial Cutting Fluid", "20L container"),
    ("P02", "Abrasive Disc Pack", "box of 50"),
    ("P03", "Protective Glove Set", "box of 100 pairs"),
]

# Purchase-size tiers (rules section 6). Every customer not listed is Small.
LARGE = ["C01", "C02", "C08", "C09", "C15"]
MEDIUM = ["C03", "C04", "C05", "C10", "C11", "C16"]
TIER_WEIGHT = {"Large": 7, "Medium": 3, "Small": 1}

# Sales-line volume by market (rules section 9). All values are Proposed.
# base_lines = lines in 2024-01; growth = annual growth; sigma = demand volatility.
MARKET_VOLUME = {
    "Thailand": {"base_lines": 28, "growth": 0.03, "sigma": 0.05},
    "Vietnam": {"base_lines": 18, "growth": 0.15, "sigma": 0.10},
    "Indonesia": {"base_lines": 13, "growth": 0.08, "sigma": 0.20},
}

# Probability that a sales line is a special-discount deal (rules section 6).
SPECIAL_PROB = {"C11": 0.45, "C18": 0.45, "C02": 0.15, "C09": 0.15, "C16": 0.15}
DEFAULT_SPECIAL_PROB = 0.03


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


def tier_of(customer_id):
    if customer_id in LARGE:
        return "Large"
    if customer_id in MEDIUM:
        return "Medium"
    return "Small"


def build_customer_profiles(customers):
    """Per-customer settings used when generating sales (not stored in the DB).

    price_adj is a fixed standing discount/premium drawn once per customer
    from Uniform(-0.04, +0.04), using its own generator seeded SEED + 1.
    """
    rng = random.Random(SEED + 1)
    profiles = {}
    for customer_id, _name, market in customers:
        tier = tier_of(customer_id)
        profiles[customer_id] = {
            "market": market,
            "tier": tier,
            "weight": TIER_WEIGHT[tier],
            "price_adj": rng.uniform(-0.04, 0.04),
            "special_prob": SPECIAL_PROB.get(customer_id, DEFAULT_SPECIAL_PROB),
        }
    return profiles


def month_starts():
    """The 24 months 2024-01 to 2025-12 as 'YYYY-MM-01' text."""
    return [f"{2024 + t // 12}-{t % 12 + 1:02d}-01" for t in range(24)]


def build_line_counts():
    """Number of sales lines for each (month_start, market).

    lines = round(base_lines * (1 + growth) ** (t / 12) * demand_factor)
    demand_factor ~ Normal(1, sigma), clipped to [0.5, 1.5], drawn once per
    market-month with its own generator seeded SEED + 2.
    """
    rng = random.Random(SEED + 2)
    counts = {}
    for t, month in enumerate(month_starts()):
        for market, v in MARKET_VOLUME.items():
            factor = min(1.5, max(0.5, rng.gauss(1.0, v["sigma"])))
            expected = v["base_lines"] * (1 + v["growth"]) ** (t / 12)
            counts[(month, market)] = round(expected * factor)
    return counts


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())

    customers = build_customers()
    conn.executemany("INSERT INTO products VALUES (?, ?, ?)", PRODUCTS)
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?)", customers)
    conn.commit()

    for table in ("products", "customers", "sales", "monthly_targets"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count} rows")

    profiles = build_customer_profiles(customers)
    print()
    print("customer profiles (not stored in the database):")
    for customer_id, p in profiles.items():
        print(
            f"{customer_id} {p['market']:<10} {p['tier']:<7} "
            f"weight={p['weight']} price_adj={p['price_adj']:+.4f} "
            f"special_prob={p['special_prob']}"
        )

    line_counts = build_line_counts()
    print()
    print("planned sales lines (not stored yet):")
    grand_total = 0
    for market in MARKET_VOLUME:
        for year in ("2024", "2025"):
            total = sum(
                n for (month, m), n in line_counts.items()
                if m == market and month.startswith(year)
            )
            grand_total += total
            print(f"{market:<10} {year}: {total}")
    print(f"total: {grand_total}")

    conn.close()


if __name__ == "__main__":
    main()
