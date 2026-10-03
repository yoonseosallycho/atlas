-- ATLAS schema (synthetic data project)
-- Grain: customers = one customer; products = one product;
--        sales = one completed sales line; monthly_targets = one market in one month.

CREATE TABLE customers (
    customer_id    TEXT PRIMARY KEY,
    customer_name  TEXT NOT NULL,
    market         TEXT NOT NULL CHECK (market IN ('Thailand', 'Vietnam', 'Indonesia'))
);

CREATE TABLE products (
    product_id    TEXT PRIMARY KEY,
    product_name  TEXT NOT NULL,
    unit_of_sale  TEXT NOT NULL
);

CREATE TABLE sales (
    sales_line_id       INTEGER PRIMARY KEY,
    sale_date           TEXT NOT NULL,
    customer_id         TEXT NOT NULL,
    product_id          TEXT NOT NULL,
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    net_unit_price_usd  REAL NOT NULL CHECK (net_unit_price_usd >= 0),
    unit_cogs_usd       REAL NOT NULL CHECK (unit_cogs_usd >= 0),
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
    FOREIGN KEY (product_id) REFERENCES products (product_id)
);

CREATE TABLE monthly_targets (
    month_start              TEXT NOT NULL,
    market                   TEXT NOT NULL CHECK (market IN ('Thailand', 'Vietnam', 'Indonesia')),
    revenue_target_usd       REAL NOT NULL CHECK (revenue_target_usd >= 0),
    gross_profit_target_usd  REAL NOT NULL,
    PRIMARY KEY (month_start, market)
);
