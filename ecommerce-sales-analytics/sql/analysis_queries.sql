-- v_line_sales: one row per completed order line with net sales and profit (reused below)
CREATE VIEW v_line_sales AS
SELECT o.order_id,
       o.customer_id,
       o.order_date,
       substr(o.order_date, 1, 7)                                   AS month,
       p.category,
       p.product_id,
       p.product_name,
       i.quantity,
       i.returned,
       i.quantity * i.unit_price * (1 - o.discount_pct / 100.0)    AS gross_sales,
       CASE WHEN i.returned = 0
            THEN i.quantity * i.unit_price * (1 - o.discount_pct / 100.0) ELSE 0 END AS net_sales,
       CASE WHEN i.returned = 0
            THEN i.quantity * (i.unit_price * (1 - o.discount_pct / 100.0) - p.unit_cost) ELSE 0 END AS gross_profit
FROM order_items i
JOIN orders   o ON o.order_id = i.order_id AND o.status = 'Completed'
JOIN products p ON p.product_id = i.product_id;

-- Q1 Monthly net sales with year-over-year growth (window function LAG)
SELECT month,
       ROUND(SUM(net_sales), 2)                                                        AS net_sales,
       COUNT(DISTINCT order_id)                                                        AS orders,
       ROUND(SUM(net_sales) / LAG(SUM(net_sales), 12) OVER (ORDER BY month) - 1, 4)   AS yoy_growth
FROM v_line_sales
GROUP BY month
ORDER BY month;

-- Q2 Top 10 products by net sales
SELECT product_id, product_name, category,
       SUM(quantity)            AS units,
       ROUND(SUM(net_sales), 2) AS net_sales
FROM v_line_sales
GROUP BY product_id, product_name, category
ORDER BY net_sales DESC
LIMIT 10;

-- Q3 Repeat-purchase rate by acquisition channel
WITH per_customer AS (
    SELECT c.acquisition_channel, v.customer_id, COUNT(DISTINCT v.order_id) AS orders, SUM(v.net_sales) AS sales
    FROM v_line_sales v JOIN customers c ON c.customer_id = v.customer_id
    GROUP BY c.acquisition_channel, v.customer_id
)
SELECT acquisition_channel,
       COUNT(*)                                          AS customers,
       ROUND(AVG(orders > 1), 4)                         AS repeat_rate,
       ROUND(AVG(sales), 2)                              AS sales_per_customer
FROM per_customer
GROUP BY acquisition_channel
ORDER BY repeat_rate DESC;

-- Q4 Category return rate and gross margin
SELECT category,
       ROUND(SUM(net_sales), 2)                          AS net_sales,
       ROUND(1 - SUM(net_sales) / SUM(gross_sales), 4)   AS return_rate,
       ROUND(SUM(gross_profit) / SUM(net_sales), 4)      AS gross_margin
FROM v_line_sales
GROUP BY category
ORDER BY net_sales DESC;

-- Q5 Customer ranking: top 10 customers by lifetime net sales (window RANK)
SELECT *
FROM (
    SELECT customer_id,
           COUNT(DISTINCT order_id)                          AS orders,
           ROUND(SUM(net_sales), 2)                          AS lifetime_sales,
           RANK() OVER (ORDER BY SUM(net_sales) DESC)        AS sales_rank
    FROM v_line_sales
    GROUP BY customer_id
)
WHERE sales_rank <= 10;
