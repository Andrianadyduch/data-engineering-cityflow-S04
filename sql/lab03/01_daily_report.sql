-- СТУДЕНТ. Блок А: виконайте три порівняння. Два останні — НАВМИСНО неправильні.
SELECT currency, COUNT(*) AS orders, SUM(total_amount) AS correct_amount
FROM lab03_cf.v_period_orders WHERE order_status = 'delivered'
GROUP BY currency ORDER BY currency;
SELECT o.currency, COUNT(*) AS joined_rows, SUM(o.total_amount) AS wrong_amount
FROM lab03_cf.v_period_orders o JOIN core.order_items i ON i.order_id = o.order_id
WHERE o.order_status = 'delivered' GROUP BY o.currency ORDER BY o.currency;
SELECT o.currency, SUM(DISTINCT o.total_amount) AS not_a_valid_fix
FROM lab03_cf.v_period_orders o JOIN core.order_items i ON i.order_id = o.order_id
WHERE o.order_status = 'delivered' GROUP BY o.currency ORDER BY o.currency;


CREATE OR REPLACE VIEW lab03_cf.v_daily_orders AS
WITH selected_orders AS (
    SELECT *
    FROM lab03_cf.v_period_orders
    WHERE order_status = 'delivered'
),
items_by_order AS (
    SELECT
        order_id,
        SUM(quantity) AS units
    FROM core.order_items
    GROUP BY order_id
),
orders_with_units AS (
    SELECT
        o.report_date,
        o.merchant_id,
        o.currency,
        o.total_amount,
        COALESCE(i.units, 0) AS units,
        CASE
            WHEN i.order_id IS NULL THEN 1
            ELSE 0
        END AS without_items
    FROM selected_orders o
    LEFT JOIN items_by_order i
        ON o.order_id = i.order_id
)
SELECT
    report_date,
    merchant_id,
    currency,
    COUNT(*) AS order_count,
    SUM(total_amount) AS order_amount,
    ROUND(AVG(total_amount), 2) AS avg_order_amount,
    SUM(units) AS accepted_units,
    SUM(without_items) AS orders_without_items
FROM orders_with_units
GROUP BY report_date, merchant_id, currency;

SELECT *
FROM lab03_cf.v_daily_orders
ORDER BY report_date, merchant_id, currency
LIMIT 10;

