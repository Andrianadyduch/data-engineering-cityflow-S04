import csv
import json
import psycopg
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

FILES = {
    "customers": BASE_DIR / "data/raw/base/customers.csv",
    "merchants": BASE_DIR / "data/raw/base/merchants.csv",
    "products": BASE_DIR / "data/raw/base/products.csv",
    "orders": BASE_DIR / "data/raw/base/orders.csv",
    "order_items": BASE_DIR / "data/raw/relational/order_items.csv",
}

EXPECTED_HEADERS = {
    "customers": [
        "customer_id", "full_name", "email", "phone",
        "city", "service_zone_id", "registered_at", "customer_status"
    ],
    "merchants": [
        "merchant_id", "merchant_name", "merchant_type",
        "city", "service_zone_id", "opened_at", "merchant_status"
    ],
    "products": [
        "product_id", "merchant_id", "product_name",
        "category", "unit_price_uah", "is_active", "updated_at"
    ],
    "orders": [
        "order_id", "customer_id", "merchant_id", "created_at",
        "order_status", "currency", "subtotal_amount",
        "delivery_fee", "discount_amount", "total_amount"
    ],
    "order_items": [
        "order_item_id", "order_id", "product_id", "quantity",
        "unit_price", "line_discount", "line_total", "currency"
    ],
}

def read_csv_files():
    for name, path in FILES.items():
        if not path.is_file():
            raise FileNotFoundError(f"Файл не знайдено: {path}")

        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)

            if reader.fieldnames != EXPECTED_HEADERS[name]:
                raise ValueError(f"Неправильні заголовки у файлі {name}")

            rows = list(reader)

            for row_number, row in enumerate(rows, start=2):
                if None in row:
                    raise ValueError(
                        f"Зайві поля у файлі {name}, рядок {row_number}"
                    )

                if any(value is None for value in row.values()):
                    raise ValueError(
                        f"Недостатньо полів у файлі {name}, рядок {row_number}"
                    )

            print(f"{name}: {len(rows)} рядків")

def load_to_staging():
    batch_id = "S04-LAB02-TEST"

    with psycopg.connect(dbname="cityflow_s04") as conn:
        with conn.cursor() as cur:
            for name, path in FILES.items():
                with path.open("r", encoding="utf-8-sig", newline="") as file:
                    reader = csv.DictReader(file)

                    if reader.fieldnames != EXPECTED_HEADERS[name]:
                        raise ValueError(f"Неправильні заголовки: {name}")

                    count = 0

                    for row_number, row in enumerate(reader, start=2):
                        if None in row or any(v is None for v in row.values()):
                            raise ValueError(
                                f"Неправильна структура CSV: {name}, рядок {row_number}"
                            )

                        cur.execute(
                            """
                            INSERT INTO stg.raw_records
                                (batch_id, source_file, source_row_number, raw_payload)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (batch_id, source_file, source_row_number)
                            DO UPDATE SET raw_payload = EXCLUDED.raw_payload
                            WHERE stg.raw_records.raw_payload = EXCLUDED.raw_payload
                            RETURNING source_row_number
                            """,
                            (batch_id, path.name, row_number, json.dumps(row))
                        )

                        if cur.fetchone() is None:
                            raise ValueError(
                                f"Змінений запис у вже завантаженому пакеті: "
                                f"{path.name}, рядок {row_number}"
                            )

                        count += 1

                        cur.execute(
                        """
                        SELECT COUNT(*)
                        FROM stg.raw_records
                        WHERE batch_id = %s AND source_file = %s
                        """,
                        (batch_id, path.name)
                    )

                    stored_count = cur.fetchone()[0]

                    if stored_count != count:
                        raise ValueError(
                            f"Кількість рядків не збігається у {path.name}: "
                            f"CSV={count}, staging={stored_count}"
                        )

    print("Завантаження в staging завершено")

if __name__ == "__main__":
    read_csv_files()
    load_to_staging()
