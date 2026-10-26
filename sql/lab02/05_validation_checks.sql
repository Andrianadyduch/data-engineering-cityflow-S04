-- 1. Перевірка дублікатів первинних ключів (PK)

SELECT 'customers' AS table_name,
       COUNT(*) - COUNT(DISTINCT customer_id) AS duplicates
FROM core.customers
UNION ALL
SELECT 'merchants', COUNT(*) - COUNT(DISTINCT merchant_id)
FROM core.merchants
UNION ALL
SELECT 'products', COUNT(*) - COUNT(DISTINCT product_id)
FROM core.products
UNION ALL
SELECT 'orders', COUNT(*) - COUNT(DISTINCT order_id)
FROM core.orders
UNION ALL
SELECT 'order_items', COUNT(*) - COUNT(DISTINCT order_item_id)
FROM core.order_items;


-- 2. Перевірка зовнішніх ключів (FK)

SELECT 'orders -> customers' AS relation,
       COUNT(*) AS missing_fk
FROM core.orders o
LEFT JOIN core.customers c ON o.customer_id = c.customer_id
WHERE c.customer_id IS NULL

UNION ALL

SELECT 'orders -> merchants', COUNT(*)
FROM core.orders o
LEFT JOIN core.merchants m ON o.merchant_id = m.merchant_id
WHERE m.merchant_id IS NULL

UNION ALL

SELECT 'products -> merchants', COUNT(*)
FROM core.products p
LEFT JOIN core.merchants m ON p.merchant_id = m.merchant_id
WHERE m.merchant_id IS NULL

UNION ALL

SELECT 'order_items -> orders', COUNT(*)
FROM core.order_items i
LEFT JOIN core.orders o ON i.order_id = o.order_id
WHERE o.order_id IS NULL

UNION ALL

SELECT 'order_items -> products', COUNT(*)
FROM core.order_items i
LEFT JOIN core.products p ON i.product_id = p.product_id
WHERE p.product_id IS NULL;


-- 3. Звірка кількості прийнятих записів із core

WITH accepted AS (
    SELECT source_file, COUNT(*) AS accepted_count
    FROM audit.row_results
    WHERE run_id = 2 AND row_status = 'accepted'
    GROUP BY source_file
),
core_counts AS (
    SELECT 'customers.csv' AS source_file,
           COUNT(*) AS core_count FROM core.customers
    UNION ALL
    SELECT 'merchants.csv', COUNT(*) FROM core.merchants
    UNION ALL
    SELECT 'products.csv', COUNT(*) FROM core.products
    UNION ALL
    SELECT 'orders.csv', COUNT(*) FROM core.orders
    UNION ALL
    SELECT 'order_items.csv', COUNT(*) FROM core.order_items
)
SELECT c.source_file,
       a.accepted_count,
       c.core_count,
       c.core_count - a.accepted_count AS difference
FROM core_counts c
JOIN accepted a USING (source_file)
ORDER BY c.source_file;


-- 3.1. Звірка сум orders.total_amount за валютами

WITH staging_sums AS (
    SELECT
        r.raw_payload->>'currency' AS currency,
        SUM((r.raw_payload->>'total_amount')::numeric) AS staging_total
    FROM stg.raw_records r
    JOIN audit.row_results a
      ON a.batch_id = r.batch_id
     AND a.source_file = r.source_file
     AND a.source_row_number = r.source_row_number
    WHERE a.run_id = 2
      AND a.row_status = 'accepted'
      AND r.source_file = 'orders.csv'
    GROUP BY r.raw_payload->>'currency'
),
core_sums AS (
    SELECT currency, SUM(total_amount) AS core_total
    FROM core.orders
    GROUP BY currency
)
SELECT
    currency,
    s.staging_total,
    c.core_total,
    c.core_total - s.staging_total AS difference
FROM core_sums c
FULL JOIN staging_sums s USING (currency)
ORDER BY currency;


-- 3.2. Звірка сум order_items.line_total за валютами

WITH staging_sums AS (
    SELECT
        r.raw_payload->>'currency' AS currency,
        SUM((r.raw_payload->>'line_total')::numeric) AS staging_total
    FROM stg.raw_records r
    JOIN audit.row_results a
      ON a.batch_id = r.batch_id
     AND a.source_file = r.source_file
     AND a.source_row_number = r.source_row_number
    WHERE a.run_id = 2
      AND a.row_status = 'accepted'
      AND r.source_file = 'order_items.csv'
    GROUP BY r.raw_payload->>'currency'
),
core_sums AS (
    SELECT currency, SUM(line_total) AS core_total
    FROM core.order_items
    GROUP BY currency
)
SELECT
    currency,
    s.staging_total,
    c.core_total,
    c.core_total - s.staging_total AS difference
FROM core_sums c
FULL JOIN staging_sums s USING (currency)
ORDER BY currency;


-- 4. Демонстрація завищення суми через JOIN

SELECT
    o.currency,
    COUNT(*) AS joined_rows,
    SUM(o.total_amount) AS incorrect_total
FROM core.orders o
JOIN core.order_items i ON o.order_id = i.order_id
GROUP BY o.currency
ORDER BY o.currency;


-- 4.1. Правильний розрахунок на рівні замовлень

SELECT
    currency,
    COUNT(*) AS orders_count,
    SUM(total_amount) AS correct_total
FROM core.orders
GROUP BY currency
ORDER BY currency;

