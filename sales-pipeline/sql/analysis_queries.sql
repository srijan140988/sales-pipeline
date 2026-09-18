-- ============================================================
-- analysis_queries.sql
-- Analysis-ready SQL queries against the star schema built by
-- etl/etl_pipeline.py. Written for PostgreSQL; works on SQLite
-- with minor date-function adjustments (noted inline).
-- ============================================================

-- 1. Monthly revenue trend
SELECT
    d.year,
    d.month,
    d.month_name,
    ROUND(SUM(f.net_revenue), 2) AS total_revenue,
    COUNT(*) AS orders
FROM fact_sales f
JOIN dim_date d ON f.date_id = d.date_id
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;


-- 2. Top 10 best-selling products by revenue
SELECT
    p.product_name,
    p.category,
    SUM(f.quantity) AS units_sold,
    ROUND(SUM(f.net_revenue), 2) AS total_revenue
FROM fact_sales f
JOIN dim_product p ON f.product_id = p.product_id
GROUP BY p.product_name, p.category
ORDER BY total_revenue DESC
LIMIT 10;


-- 3. Regional performance summary
SELECT
    r.region_name,
    COUNT(*) AS orders,
    ROUND(SUM(f.net_revenue), 2) AS total_revenue,
    ROUND(AVG(f.net_revenue), 2) AS avg_order_value
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
GROUP BY r.region_name
ORDER BY total_revenue DESC;


-- 4. Category performance with discount impact
SELECT
    p.category,
    ROUND(SUM(f.gross_revenue), 2) AS gross_revenue,
    ROUND(SUM(f.gross_revenue - f.net_revenue), 2) AS discount_given,
    ROUND(SUM(f.net_revenue), 2) AS net_revenue,
    ROUND(100.0 * SUM(f.gross_revenue - f.net_revenue) / NULLIF(SUM(f.gross_revenue), 0), 2) AS discount_pct_of_gross
FROM fact_sales f
JOIN dim_product p ON f.product_id = p.product_id
GROUP BY p.category
ORDER BY net_revenue DESC;


-- 5. Top 10 customers by lifetime value
SELECT
    c.customer_id,
    c.customer_name,
    COUNT(*) AS orders,
    ROUND(SUM(f.net_revenue), 2) AS lifetime_value
FROM fact_sales f
JOIN dim_customer c ON f.customer_id = c.customer_id
GROUP BY c.customer_id, c.customer_name
ORDER BY lifetime_value DESC
LIMIT 10;


-- 6. Sales channel & payment method breakdown
SELECT
    sales_channel,
    payment_method,
    COUNT(*) AS orders,
    ROUND(SUM(net_revenue), 2) AS total_revenue
FROM fact_sales
GROUP BY sales_channel, payment_method
ORDER BY total_revenue DESC;


-- 7. Weekday vs weekend performance
SELECT
    d.is_weekend,
    COUNT(*) AS orders,
    ROUND(SUM(f.net_revenue), 2) AS total_revenue,
    ROUND(AVG(f.net_revenue), 2) AS avg_order_value
FROM fact_sales f
JOIN dim_date d ON f.date_id = d.date_id
GROUP BY d.is_weekend;


-- 8. Month-over-month revenue growth (%) using window functions
SELECT
    year,
    month,
    month_name,
    total_revenue,
    ROUND(
        100.0 * (total_revenue - LAG(total_revenue) OVER (ORDER BY year, month))
        / NULLIF(LAG(total_revenue) OVER (ORDER BY year, month), 0),
        2
    ) AS mom_growth_pct
FROM (
    SELECT
        d.year, d.month, d.month_name,
        SUM(f.net_revenue) AS total_revenue
    FROM fact_sales f
    JOIN dim_date d ON f.date_id = d.date_id
    GROUP BY d.year, d.month, d.month_name
) monthly
ORDER BY year, month;


-- 9. Top product per region (window function rank)
SELECT region_name, product_name, category, total_revenue
FROM (
    SELECT
        r.region_name,
        p.product_name,
        p.category,
        SUM(f.net_revenue) AS total_revenue,
        RANK() OVER (PARTITION BY r.region_name ORDER BY SUM(f.net_revenue) DESC) AS rnk
    FROM fact_sales f
    JOIN dim_region r ON f.region_id = r.region_id
    JOIN dim_product p ON f.product_id = p.product_id
    GROUP BY r.region_name, p.product_name, p.category
) ranked
WHERE rnk = 1
ORDER BY total_revenue DESC;
