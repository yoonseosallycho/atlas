-- Total revenue and data period for the ATLAS home screen (all data is synthetic).
-- One row. Revenue = quantity x net unit price, summed over every sales line.
-- Used by app/streamlit_app.py.

SELECT
    ROUND(SUM(quantity * net_unit_price_usd), 2)  AS total_revenue_usd,
    COUNT(*)                                      AS sales_lines,
    MIN(sale_date)                                AS first_sale_date,
    MAX(sale_date)                                AS last_sale_date,
    COUNT(DISTINCT substr(sale_date, 1, 7))       AS months_with_sales
FROM sales;
