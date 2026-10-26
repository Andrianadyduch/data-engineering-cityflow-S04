# ER-діаграма PostgreSQL — Lab 02

```mermaid
erDiagram
    customers {
        TEXT customer_id PK "NOT NULL"
        TEXT full_name "NOT NULL"
        TEXT city "NULL"
        TIMESTAMPTZ registered_at "NULL"
    }

    merchants {
        TEXT merchant_id PK "NOT NULL"
        TEXT merchant_name "NOT NULL"
        TEXT city "NULL"
        TIMESTAMPTZ opened_at "NULL"
    }

    products {
        TEXT product_id PK "NOT NULL"
        TEXT merchant_id FK "NOT NULL"
        TEXT product_name "NOT NULL"
        NUMERIC_12_2 unit_price_uah "NOT NULL"
        BOOLEAN is_active "NOT NULL"
    }

    orders {
        TEXT order_id PK "NOT NULL"
        TEXT customer_id FK "NOT NULL"
        TEXT merchant_id FK "NOT NULL"
        TIMESTAMPTZ created_at "NOT NULL"
        TEXT order_status "NOT NULL"
        TEXT currency "NOT NULL"
        NUMERIC_12_2 subtotal_amount "NOT NULL"
        NUMERIC_12_2 delivery_fee "NOT NULL"
        NUMERIC_12_2 discount_amount "NOT NULL"
        NUMERIC_12_2 total_amount "NOT NULL"
    }

    order_items {
        TEXT order_item_id PK "NOT NULL"
        TEXT order_id FK "NOT NULL"
        TEXT product_id FK "NOT NULL"
        INTEGER quantity "NOT NULL"
        NUMERIC_12_2 unit_price "NOT NULL"
        NUMERIC_12_2 line_discount "NOT NULL"
        NUMERIC_12_2 line_total "NOT NULL"
        TEXT currency "NOT NULL"
    }

    customers ||--o{ orders : places
    merchants ||--o{ orders : receives
    merchants ||--o{ products : offers
    orders ||--o{ order_items : contains
    products ||--o{ order_items : referenced_by


```

- customers — один рядок на одного клієнта.
- merchants — один рядок на одного продавця.
- products — один рядок на один товар.
- orders — один рядок на одне замовлення.
- order_items — один рядок на одну позицію замовлення.

Усі первинні ключі — стабільні бізнес-ідентифікатори типу TEXT.

## Схеми PostgreSQL

- stg — початкові дані та метадані завантаження.
- core — перевірені бізнес-дані.
- audit — результати перевірок та історія запусків.
