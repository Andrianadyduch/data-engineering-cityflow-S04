CREATE TABLE IF NOT EXISTS core.customers (
    customer_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    city TEXT,
    registered_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS core.merchants (
    merchant_id TEXT PRIMARY KEY,
    merchant_name TEXT NOT NULL,
    city TEXT,
    opened_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS core.products (
    product_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL REFERENCES core.merchants(merchant_id),
    product_name TEXT NOT NULL,
    unit_price_uah NUMERIC(12,2) NOT NULL,
    is_active BOOLEAN NOT NULL,
    CONSTRAINT chk_product_price CHECK (
        unit_price_uah >= 0 AND
        (NOT is_active OR unit_price_uah > 0)
    )
);

CREATE TABLE IF NOT EXISTS core.orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES core.customers(customer_id),
    merchant_id TEXT NOT NULL REFERENCES core.merchants(merchant_id),
    created_at TIMESTAMPTZ NOT NULL,
    order_status TEXT NOT NULL,
    currency TEXT NOT NULL CHECK (currency IN ('UAH', 'USD', 'EUR')),
    subtotal_amount NUMERIC(12,2) NOT NULL CHECK (subtotal_amount >= 0),
    delivery_fee NUMERIC(12,2) NOT NULL CHECK (delivery_fee >= 0),
    discount_amount NUMERIC(12,2) NOT NULL CHECK (discount_amount >= 0),
    total_amount NUMERIC(12,2) NOT NULL CHECK (total_amount >= 0)
);

CREATE TABLE IF NOT EXISTS core.order_items (
    order_item_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES core.orders(order_id),
    product_id TEXT NOT NULL REFERENCES core.products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
    line_discount NUMERIC(12,2) NOT NULL CHECK (line_discount >= 0),
    line_total NUMERIC(12,2) NOT NULL CHECK (line_total >= 0),
    currency TEXT NOT NULL CHECK (currency IN ('UAH', 'USD', 'EUR'))
);
