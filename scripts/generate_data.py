"""ATLAS data generator, step 5: build the database from the schema file,
load the fixed reference tables (products, customers), create the
customer profiles, plan sales lines per market-month, assign each line a
date, customer, product and quantity, price and cost every line, and store
the sales lines, and create the monthly targets from the plan assumptions.

Rules: docs/DATA_GENERATION_RULES.md (v0.2). All data is synthetic.
"""
import csv
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

# Product mix and quantity per sales line (rules section 5). Proposed values.
PRODUCT_MIX = {"P01": 40, "P02": 35, "P03": 25}  # relative weights (percent)
MEDIAN_QTY = {"P01": 20, "P02": 40, "P03": 15}  # units of sale per line
QTY_SIGMA = 0.4

# Price and cost rules (rules sections 5 and 7). Base values are per unit of sale.
BASE_PRICE = {"P01": 100.0, "P02": 60.0, "P03": 150.0}
BASE_COGS = {"P01": 70.0, "P02": 45.0, "P03": 95.0}
TXN_NOISE = 0.04  # per-line price variation, +/- 4%
PRICE_MULTIPLIER_RANGE = (0.92, 1.08)  # normal lines stay within +/- 8%
SPECIAL_DEPTH = (0.12, 0.30)  # extra discount on special-discount lines
COGS_NOISE = 0.03  # per-line cost variation, +/- 3%

# Monthly target plan (rules section 10). All values are Proposed planning
# assumptions fixed before generation; they never use generated sales.
# (market, year, start monthly revenue USD, plan annual growth, planned gross margin)
TARGET_PLAN = [
    ("Thailand", 2024, 65000, 0.04, 0.29),
    ("Thailand", 2025, 67600, 0.04, 0.29),
    ("Vietnam", 2024, 40000, 0.18, 0.28),
    ("Vietnam", 2025, 47200, 0.15, 0.28),
    ("Indonesia", 2024, 30000, 0.10, 0.27),
    ("Indonesia", 2025, 33000, 0.10, 0.27),
]

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


def build_sales_lines(line_counts, profiles):
    """Sales lines with date, customer, product and quantity (no prices yet).

    Customer, product and day are drawn with a generator seeded SEED + 3;
    quantities with a generator seeded SEED + 4. Customers are chosen in
    proportion to their tier weight within the market. The day (1-28) uses
    the assignment generator because the rules do not name a separate seed.
    Lines are then sorted by date and numbered 1, 2, 3, ...
    """
    rng_assign = random.Random(SEED + 3)
    rng_qty = random.Random(SEED + 4)
    product_ids = list(PRODUCT_MIX)
    product_weights = list(PRODUCT_MIX.values())

    lines = []
    for (month, market), n_lines in line_counts.items():
        ids = [cid for cid, p in profiles.items() if p["market"] == market]
        weights = [profiles[cid]["weight"] for cid in ids]
        for _ in range(n_lines):
            customer_id = rng_assign.choices(ids, weights=weights)[0]
            product_id = rng_assign.choices(product_ids, weights=product_weights)[0]
            day = rng_assign.randint(1, 28)
            noise = rng_qty.lognormvariate(0, QTY_SIGMA)
            quantity = max(1, round(MEDIAN_QTY[product_id] * noise))
            lines.append(
                {
                    "sale_date": f"{month[:8]}{day:02d}",
                    "customer_id": customer_id,
                    "product_id": product_id,
                    "quantity": quantity,
                }
            )

    lines.sort(key=lambda r: (r["sale_date"], r["customer_id"], r["product_id"]))
    for number, line in enumerate(lines, start=1):
        line["sales_line_id"] = number
    return lines


def add_prices_and_costs(lines, profiles):
    """Add net_unit_price_usd and unit_cogs_usd to every line.

    Order of steps for each line (rules section 7):
      1. normal price = base price * (1 + customer price_adj + line noise),
         kept within +/- 8% of base (generator SEED + 5)
      2. decide whether it is a special-discount deal, using the customer's
         probability (generator SEED + 6)
      3. if special, take an extra 12-30% off the normal price (SEED + 6)
      4. round the price to 2 decimals
    Unit cost = base cost * (1 + noise within +/- 3%) (generator SEED + 7).
    Lines are processed in sales_line_id order so results are reproducible.
    """
    rng_price = random.Random(SEED + 5)
    rng_special = random.Random(SEED + 6)
    rng_cost = random.Random(SEED + 7)

    for line in lines:
        profile = profiles[line["customer_id"]]
        product_id = line["product_id"]

        multiplier = 1 + profile["price_adj"] + rng_price.uniform(-TXN_NOISE, TXN_NOISE)
        low, high = PRICE_MULTIPLIER_RANGE
        multiplier = min(high, max(low, multiplier))
        price = BASE_PRICE[product_id] * multiplier

        is_special = rng_special.random() < profile["special_prob"]
        special_pct = 0.0
        if is_special:
            special_pct = rng_special.uniform(*SPECIAL_DEPTH)
            price = price * (1 - special_pct)

        cogs = BASE_COGS[product_id] * (1 + rng_cost.uniform(-COGS_NOISE, COGS_NOISE))

        line["net_unit_price_usd"] = round(price, 2)
        line["unit_cogs_usd"] = round(cogs, 2)
        line["is_special"] = is_special
        line["special_pct"] = round(special_pct, 4)


def build_monthly_targets():
    """72 target rows: 3 markets x 24 months, from the plan only.

    revenue_target = start_revenue * (1 + growth) ** ((m - 1) / 12), m = 1..12
    gross_profit_target = revenue_target * planned_margin
    Both are rounded to 2 decimals. No random numbers and no sales data are used.
    """
    rows = []
    for market, year, start, growth, margin in TARGET_PLAN:
        for m in range(1, 13):
            revenue = start * (1 + growth) ** ((m - 1) / 12)
            rows.append(
                (f"{year}-{m:02d}-01", market, round(revenue, 2), round(revenue * margin, 2))
            )
    return rows


def write_generation_log(lines):
    """Helper file for validation only (kept out of Git by .gitignore)."""
    path = ROOT / "generation_log.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sales_line_id", "is_special_discount", "special_discount_pct"])
        for r in lines:
            writer.writerow([r["sales_line_id"], int(r["is_special"]), r["special_pct"]])


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())

    customers = build_customers()
    profiles = build_customer_profiles(customers)
    line_counts = build_line_counts()
    lines = build_sales_lines(line_counts, profiles)
    add_prices_and_costs(lines, profiles)
    targets = build_monthly_targets()

    conn.executemany("INSERT INTO products VALUES (?, ?, ?)", PRODUCTS)
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?)", customers)
    conn.executemany(
        "INSERT INTO sales (sales_line_id, sale_date, customer_id, product_id, "
        "quantity, net_unit_price_usd, unit_cogs_usd) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                r["sales_line_id"], r["sale_date"], r["customer_id"], r["product_id"],
                r["quantity"], r["net_unit_price_usd"], r["unit_cogs_usd"],
            )
            for r in lines
        ],
    )
    conn.executemany("INSERT INTO monthly_targets VALUES (?, ?, ?, ?)", targets)
    conn.commit()
    write_generation_log(lines)

    for table in ("products", "customers", "sales", "monthly_targets"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count} rows")
    special = sum(1 for r in lines if r["is_special"])
    print(f"special-discount lines (from generation log): {special}")
    print("wrote generation_log.csv")

    conn.close()


if __name__ == "__main__":
    main()
