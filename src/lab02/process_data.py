import json
from decimal import Decimal
import psycopg
from psycopg.types.json import Jsonb
from validate_data import validate_currency, validate_amount, validate_quantity, validate_date, parse_date

DB_NAME = "cityflow_s04"
BATCH_ID = "S04-LAB02-TEST"
SOURCE_FILES = ("customers.csv", "merchants.csv", "products.csv", "orders.csv", "order_items.csv")
ID_FIELDS = dict(zip(SOURCE_FILES, ("customer_id", "merchant_id", "product_id", "order_id", "order_item_id")))

FOREIGN_KEYS = {
    "products.csv": {"merchant_id": "merchants.csv"},
    "orders.csv": {"customer_id": "customers.csv", "merchant_id": "merchants.csv"},
    "order_items.csv": {"order_id": "orders.csv", "product_id": "products.csv"},
}

AMOUNT_FIELDS = {
    "products.csv": ("unit_price_uah",),
    "orders.csv": ("subtotal_amount", "delivery_fee", "discount_amount", "total_amount"),
    "order_items.csv": ("unit_price", "line_discount", "line_total"),
}

DATE_FIELDS = {
    "customers.csv": ("registered_at",),
    "merchants.csv": ("opened_at",),
    "orders.csv": ("created_at",),
}

INSERTS = {
    "customers.csv": (
        "INSERT INTO core.customers (customer_id, full_name, city, registered_at) VALUES (%s,%s,%s,%s)",
        lambda p: (p["customer_id"], p["full_name"], p.get("city"), parse_date(p["registered_at"]))
    ),
    "merchants.csv": (
        "INSERT INTO core.merchants (merchant_id, merchant_name, city, opened_at) VALUES (%s,%s,%s,%s)",
        lambda p: (p["merchant_id"], p["merchant_name"], p.get("city"), parse_date(p["opened_at"]))
    ),
    "products.csv": (
        "INSERT INTO core.products (product_id, merchant_id, product_name, unit_price_uah, is_active) VALUES (%s,%s,%s,%s,%s)",
        lambda p: (p["product_id"], p["merchant_id"], p["product_name"], Decimal(p["unit_price_uah"]), str(p["is_active"]).lower() == "true")
    ),
    "orders.csv": (
        "INSERT INTO core.orders (order_id, customer_id, merchant_id, created_at, order_status, currency, subtotal_amount, delivery_fee, discount_amount, total_amount) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        lambda p: (p["order_id"], p["customer_id"], p["merchant_id"], parse_date(p["created_at"]), p["order_status"], p["currency"], *(Decimal(p[k]) for k in AMOUNT_FIELDS["orders.csv"]))
    ),
    "order_items.csv": (
        "INSERT INTO core.order_items (order_item_id, order_id, product_id, quantity, unit_price, line_discount, line_total, currency) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        lambda p: (p["order_item_id"], p["order_id"], p["product_id"], int(p["quantity"]), *(Decimal(p[k]) for k in AMOUNT_FIELDS["order_items.csv"]), p["currency"])
    ),
}


def get_record_id(source_file, payload):
    value = payload.get(ID_FIELDS[source_file])
    return value.strip() if isinstance(value, str) else ""


def validate_record(source_file, payload):
    if not get_record_id(source_file, payload):
        return "rejected", "Порожній ідентифікатор"

    if source_file in ("orders.csv", "order_items.csv") and not validate_currency(payload.get("currency")):
        return "rejected", f"Некоректна валюта: {payload.get('currency')}"

    for field in AMOUNT_FIELDS.get(source_file, ()):
        if not validate_amount(payload.get(field)):
            return "rejected", f"Некоректна сума в полі {field}"

    if source_file == "order_items.csv" and not validate_quantity(payload.get("quantity")):
        return "rejected", "Некоректна кількість товару"

    for field in DATE_FIELDS.get(source_file, ()):
        if not validate_date(payload.get(field)):
            return "rejected", f"Некоректна дата в полі {field}"

    if source_file == "products.csv":
        active = str(payload.get("is_active", "")).lower()
        if active not in ("true", "false"):
            return "rejected", "Некоректне значення is_active"
        try:
            price = Decimal(payload.get("unit_price_uah", ""))
        except Exception:
            return "rejected", "Некоректна ціна товару"
        if active == "true" and price <= 0:
            return "rejected", "Активний товар має нульову або від'ємну ціну"

    return "accepted", None


def start_audit_run(batch_id=BATCH_ID):
    with psycopg.connect(dbname=DB_NAME) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO audit.load_runs (batch_id, status) VALUES (%s, 'running') RETURNING run_id",
            (batch_id,)
        )
        return cur.fetchone()[0]


def classify_all_records(batch_id=BATCH_ID):
    with psycopg.connect(dbname=DB_NAME) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT source_file, source_row_number, raw_payload FROM stg.raw_records WHERE batch_id=%s ORDER BY source_file, source_row_number",
            (batch_id,)
        )
        records = {name: [] for name in SOURCE_FILES}
        for name, number, payload in cur.fetchall():
            records.setdefault(name, []).append({"row_number": number, "payload": payload})

    missing = [name for name in SOURCE_FILES if not records.get(name)]
    if missing:
        raise ValueError("Відсутні дані staging для файлів: " + ", ".join(missing))

    results, groups = {}, {}

    for name, rows in records.items():
        for row in rows:
            key, payload = (name, row["row_number"]), row["payload"]
            status, reason = validate_record(name, payload)
            results[key] = {"status": status, "reason": reason, "payload": payload}

            business_id = get_record_id(name, payload)
            if business_id:
                groups.setdefault((name, business_id), []).append(key)

    for (_, business_id), keys in groups.items():
        if len(keys) < 2:
            continue

        signatures = {
            json.dumps(results[k]["payload"], sort_keys=True, ensure_ascii=False)
            for k in keys
        }

        if len(signatures) > 1:
            for key in keys:
                results[key].update(
                    status="rejected",
                    reason=f"Конфліктні версії бізнес-ключа {business_id}"
                )
        else:
            for key in sorted(keys, key=lambda k: k[1])[1:]:
                results[key].update(status="duplicate", reason="Точний дублікат запису")

    changed = True
    while changed:
        changed = False
        accepted = {name: set() for name in SOURCE_FILES}

        for (name, _), result in results.items():
            if result["status"] == "accepted":
                accepted[name].add(get_record_id(name, result["payload"]))

        for (name, _), result in results.items():
            if result["status"] != "accepted":
                continue

            for field, parent in FOREIGN_KEYS.get(name, {}).items():
                reference = result["payload"].get(field, "")
                if reference not in accepted[parent]:
                    result.update(
                        status="rejected",
                        reason=f"Не знайдено прийнятий запис {parent}, поле {ID_FIELDS[parent]}: {reference}"
                    )
                    changed = True
                    break

    return records, results


def reason_code(result):
    reason, status = result["reason"] or "", result["status"]

    if status == "duplicate":
        return "DUPLICATE"

    for fragment, code in (
        ("Не знайдено прийнятий запис", "MISSING_FK"),
        ("Некоректна дата", "INVALID_DATE"),
        ("Некоректна валюта", "INVALID_CURRENCY"),
        ("Активний товар має", "INVALID_PRICE")
    ):
        if fragment in reason:
            return code

    return "VALIDATION_ERROR" if status == "rejected" else None


def save_classification_results(run_id, batch_id=BATCH_ID):
    _, results = classify_all_records(batch_id)
    counts = {
        name: {"input": 0, "accepted": 0, "rejected": 0, "duplicate": 0}
        for name in SOURCE_FILES
    }

    with psycopg.connect(dbname=DB_NAME) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT status FROM audit.load_runs WHERE run_id=%s AND batch_id=%s",
            (run_id, batch_id)
        )
        row = cur.fetchone()
        if row is None or row[0] != "running":
            raise ValueError("Не знайдено активний run для запису аудиту")

        for (name, number), result in sorted(results.items()):
            payload = result["payload"]
            cur.execute(
                """INSERT INTO audit.row_results
                (run_id,batch_id,source_file,source_row_number,business_key,row_status,reason_code,reason,raw_payload)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    run_id, batch_id, name, number,
                    get_record_id(name, payload) or None,
                    result["status"], reason_code(result),
                    result["reason"], Jsonb(payload)
                )
            )
            counts[name]["input"] += 1
            counts[name][result["status"]] += 1

        for name, c in counts.items():
            if c["input"] != c["accepted"] + c["rejected"] + c["duplicate"]:
                raise ValueError(f"Статистика не сходиться для {name}")

            cur.execute(
                """INSERT INTO audit.file_stats
                (run_id,source_file,input_count,accepted_count,rejected_count,duplicate_count)
                VALUES (%s,%s,%s,%s,%s,%s)""",
                (
                    run_id, name, c["input"], c["accepted"],
                    c["rejected"], c["duplicate"]
                )
            )

    for name, c in sorted(counts.items()):
        print(f"{name}: accepted={c['accepted']}, rejected={c['rejected']}, duplicate={c['duplicate']}")
    print(f"Оброблено рядків: {sum(c['input'] for c in counts.values())}")
    return counts


def check_core(cur, run_id, expected):
    cur.execute(
        "SELECT (SELECT COUNT(*) FROM core.customers), (SELECT COUNT(*) FROM core.merchants), (SELECT COUNT(*) FROM core.products), (SELECT COUNT(*) FROM core.orders), (SELECT COUNT(*) FROM core.order_items)"
    )
    counts = cur.fetchone()

    if counts != tuple(expected.get(name, 0) for name in SOURCE_FILES):
        raise ValueError(f"Кількість core не збігається: actual={counts}, expected={expected}")

    for name, sql in (
        ("orders_without_customer", "SELECT COUNT(*) FROM core.orders o LEFT JOIN core.customers c USING(customer_id) WHERE c.customer_id IS NULL"),
        ("orders_without_merchant", "SELECT COUNT(*) FROM core.orders o LEFT JOIN core.merchants m USING(merchant_id) WHERE m.merchant_id IS NULL"),
        ("products_without_merchant", "SELECT COUNT(*) FROM core.products p LEFT JOIN core.merchants m USING(merchant_id) WHERE m.merchant_id IS NULL"),
        ("items_without_order", "SELECT COUNT(*) FROM core.order_items i LEFT JOIN core.orders o USING(order_id) WHERE o.order_id IS NULL"),
        ("items_without_product", "SELECT COUNT(*) FROM core.order_items i LEFT JOIN core.products p USING(product_id) WHERE p.product_id IS NULL")
    ):
        cur.execute(sql)
        count = cur.fetchone()[0]
        if count:
            raise ValueError(f"Перевірка зовнішнього ключа {name}: {count} помилок")

    for source, column, table in (
        ("orders.csv", "total_amount", "orders"),
        ("order_items.csv", "line_total", "order_items")
    ):
        cur.execute(
            f"""SELECT raw_payload->>'currency', SUM((raw_payload->>'{column}')::numeric)
            FROM audit.row_results
            WHERE run_id=%s AND source_file=%s AND row_status='accepted'
            GROUP BY raw_payload->>'currency'""",
            (run_id, source)
        )
        expected_sums = dict(cur.fetchall())

        cur.execute(f"SELECT currency, SUM({column}) FROM core.{table} GROUP BY currency")
        actual_sums = dict(cur.fetchall())

        if expected_sums != actual_sums:
            raise ValueError(
                f"Звірка {table}.{column} за currency не пройшла: expected={expected_sums}, actual={actual_sums}"
            )


def mark_failed(run_id):
    with psycopg.connect(dbname=DB_NAME) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE audit.load_runs SET status='failed', finished_at=NOW() WHERE run_id=%s AND status='running'",
            (run_id,)
        )


def load_accepted_to_core(run_id, batch_id=BATCH_ID, fail_after_delete=False):
    try:
        with psycopg.connect(dbname=DB_NAME) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM audit.load_runs WHERE run_id=%s AND batch_id=%s FOR UPDATE",
                (run_id, batch_id)
            )
            row = cur.fetchone()
            if row is None or row[0] != "running":
                raise ValueError("Потрібен активний запуск")

            cur.execute(
                "SELECT source_file, accepted_count FROM audit.file_stats WHERE run_id=%s",
                (run_id,)
            )
            expected = dict(cur.fetchall())

            cur.execute(
                "SELECT source_file, COUNT(*) FROM audit.row_results WHERE run_id=%s AND row_status='accepted' GROUP BY source_file",
                (run_id,)
            )
            actual = dict(cur.fetchall())

            if expected != actual:
                raise ValueError(f"Аудит не збігається: expected={expected}, actual={actual}")

            cur.execute(
                "SELECT source_file, raw_payload FROM audit.row_results WHERE run_id=%s AND row_status='accepted' ORDER BY source_file, source_row_number",
                (run_id,)
            )
            records = {name: [] for name in SOURCE_FILES}
            for name, payload in cur.fetchall():
                records[name].append(payload)

            cur.execute(
                "TRUNCATE core.order_items, core.orders, core.products, core.customers, core.merchants"
            )

            if fail_after_delete:
                cur.execute(
                    "INSERT INTO core.order_items (order_item_id,order_id,product_id,quantity,unit_price,line_discount,line_total,currency) VALUES ('ROLLBACK-TEST','missing-order','missing-product',-1,0,0,0,'UAH')"
                )

            for name in SOURCE_FILES:
                sql, convert = INSERTS[name]
                for payload in records[name]:
                    cur.execute(sql, convert(payload))

            check_core(cur, run_id, expected)

            cur.execute(
                "UPDATE audit.load_runs SET status='success', finished_at=NOW() WHERE run_id=%s",
                (run_id,)
            )

        print("Завантаження завершено успішно; snapshot та аудит опубліковано.")

    except Exception:
        mark_failed(run_id)
        raise


def run_pipeline(batch_id=BATCH_ID, fail_after_delete=False):
    run_id = start_audit_run(batch_id)
    try:
        save_classification_results(run_id, batch_id)
        load_accepted_to_core(run_id, batch_id, fail_after_delete=fail_after_delete)
        return run_id
    except Exception:
        mark_failed(run_id)
        raise


if __name__ == "__main__":
    run_pipeline()
