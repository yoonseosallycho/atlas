-- ATLAS foundation checks for atlas.db (all data is synthetic).
-- Run from the project folder:
--   sqlite3 -header -column atlas.db < sql/02_validation.sql
--
-- Part 1: one row per check. status is PASS when actual equals expected.
-- Part 2: monthly revenue targets summed by market and year.

SELECT check_name, actual, expected,
       CASE WHEN actual = expected THEN 'PASS' ELSE 'FAIL' END AS status
FROM (
    -- Row counts
    SELECT 'products: row count' AS check_name, COUNT(*) AS actual, 3 AS expected
        FROM products
    UNION ALL SELECT 'customers: row count', COUNT(*), 20 FROM customers
    UNION ALL SELECT 'sales: row count', COUNT(*), 1529 FROM sales
    UNION ALL SELECT 'monthly_targets: row count', COUNT(*), 72 FROM monthly_targets
    -- Unique keys (rows minus distinct keys; 0 means no duplicates)
    UNION ALL SELECT 'sales: duplicate sales_line_id',
        COUNT(*) - COUNT(DISTINCT sales_line_id), 0 FROM sales
    UNION ALL SELECT 'customers: duplicate customer_id',
        COUNT(*) - COUNT(DISTINCT customer_id), 0 FROM customers
    UNION ALL SELECT 'products: duplicate product_id',
        COUNT(*) - COUNT(DISTINCT product_id), 0 FROM products
    UNION ALL SELECT 'targets: duplicate month and market',
        COUNT(*) - (SELECT COUNT(*) FROM
            (SELECT DISTINCT month_start, market FROM monthly_targets)),
        0 FROM monthly_targets
    -- References (sales rows whose customer or product does not exist)
    UNION ALL SELECT 'sales: unknown customer_id', COUNT(*), 0 FROM sales
        WHERE customer_id NOT IN (SELECT customer_id FROM customers)
    UNION ALL SELECT 'sales: unknown product_id', COUNT(*), 0 FROM sales
        WHERE product_id NOT IN (SELECT product_id FROM products)
    -- Target coverage: 24 months x 3 markets, no duplicates = 72 distinct pairs
    UNION ALL SELECT 'targets: distinct months',
        COUNT(DISTINCT month_start), 24 FROM monthly_targets
    UNION ALL SELECT 'targets: distinct markets',
        COUNT(DISTINCT market), 3 FROM monthly_targets
    UNION ALL SELECT 'targets: first month',
        MIN(month_start), '2024-01-01' FROM monthly_targets
    UNION ALL SELECT 'targets: last month',
        MAX(month_start), '2025-12-01' FROM monthly_targets
    -- Value rules
    UNION ALL SELECT 'sales: invalid quantity/price/cost', COUNT(*), 0 FROM sales
        WHERE quantity <= 0 OR net_unit_price_usd < 0 OR unit_cogs_usd < 0
    -- Revenue = quantity x price, summed. The second line repeats it after joining
    -- to customers; the same total means no sale was lost or duplicated by the join.
    UNION ALL SELECT 'revenue: total USD',
        ROUND(SUM(quantity * net_unit_price_usd), 2), 3634227.59 FROM sales
    UNION ALL SELECT 'revenue: total USD via customers join',
        ROUND(SUM(s.quantity * s.net_unit_price_usd), 2), 3634227.59
        FROM sales AS s JOIN customers AS c ON c.customer_id = s.customer_id
);

SELECT market,
       substr(month_start, 1, 4) AS year,
       ROUND(SUM(revenue_target_usd), 2) AS revenue_target_usd
FROM monthly_targets
GROUP BY market, substr(month_start, 1, 4)
ORDER BY market, year;
