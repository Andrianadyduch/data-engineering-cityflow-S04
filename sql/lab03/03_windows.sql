CREATE OR REPLACE VIEW lab03_cf.v_running_orders AS
SELECT
    report_date,
    merchant_id,
    currency,
    order_amount,
    SUM(order_amount) OVER (
        PARTITION BY merchant_id, currency
        ORDER BY report_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_amount
FROM lab03_cf.v_daily_orders;

CREATE OR REPLACE VIEW lab03_cf.v_latest_customer_order AS
WITH numbered_orders AS (
    SELECT
        customer_id,
        order_id,
        merchant_id,
        created_at,
        order_status,
        currency,
        total_amount,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY created_at DESC, order_id DESC
        ) AS rn
    FROM lab03_cf.v_period_orders
)
SELECT
    customer_id,
    order_id,
    merchant_id,
    created_at,
    order_status,
    currency,
    total_amount
FROM numbered_orders
WHERE rn = 1;

SELECT *
FROM lab03_cf.v_running_orders
ORDER BY merchant_id, currency, report_date
LIMIT 10;

SELECT *
FROM lab03_cf.v_latest_customer_order
ORDER BY customer_id
LIMIT 10;

