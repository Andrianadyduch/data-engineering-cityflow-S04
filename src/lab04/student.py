import csv
import hashlib
import io
import json
import logging
import time
import zipfile
from pathlib import Path
from typing import Any, Callable

import requests
from support import CSV_COLUMNS, save_response

LOG = logging.getLogger("lab04")

def read_file_batch(
    package_path: Path,
    student_id: str
) -> dict[str, list[dict[str, str]]]:

    result = {}

    try:
        with zipfile.ZipFile(package_path, "r") as archive:
            manifest = json.loads(
                archive.read("PACKAGE_INFO.json")
            )

            if manifest.get("student_id") != student_id:
                raise ValueError("Неправильний student_id")

            for file_info in manifest["files"]:
                filename = file_info["path"]
                content = archive.read(filename)

                if len(content) != file_info["size_bytes"]:
                    raise ValueError(
                        f"Неправильний розмір файлу: {filename}"
                    )

                checksum = hashlib.sha256(content).hexdigest()

                if checksum != file_info["sha256"]:
                    raise ValueError(
                        f"Неправильна SHA-256: {filename}"
                    )

            for table in ("orders", "order_items"):
                filename = f"{table}.csv"

                content = archive.read(filename).decode("utf-8")
                reader = csv.DictReader(io.StringIO(content))

                if reader.fieldnames != CSV_COLUMNS[table]:
                    raise ValueError(
                        f"Неправильні заголовки: {filename}"
                    )

                rows = []

                for row in reader:
                    if None in row or any(
                        value is None for value in row.values()
                    ):
                        raise ValueError(
                            f"Некоректний рядок: {filename}"
                        )

                    rows.append(row)

                result[table] = rows

    except (
        KeyError,
        zipfile.BadZipFile,
        UnicodeDecodeError,
        json.JSONDecodeError
    ) as error:
        raise ValueError(
            f"Помилка структури ZIP: {error}"
        ) from error

    return result

def request_page(
    session: requests.Session,
    url: str,
    *,
    params: dict,
    headers: dict,
    timeout: tuple[float, float] = (3, 10),
    max_attempts: int = 4,
    sleep: Callable[[float], None] = time.sleep
) -> requests.Response:

    retry_statuses = {429, 500, 502, 503, 504}

    if max_attempts < 1:
        raise ValueError("max_attempts має бути додатним")

    for attempt in range(max_attempts):
        response = None

        try:
            response = session.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
                allow_redirects=False
            )

            if response.status_code == 200:
                return response

            if response.status_code not in retry_statuses:
                response.raise_for_status()
                raise ValueError(
                    f"Неочікуваний HTTP статус: "
                    f"{response.status_code}"
                )

            response.raise_for_status()

        except requests.exceptions.SSLError:
            raise

        except (requests.Timeout, requests.ConnectionError):
            if attempt == max_attempts - 1:
                raise

        except requests.HTTPError:
            if (
                response is None
                or response.status_code not in retry_statuses
            ):
                raise

            if attempt == max_attempts - 1:
                raise

        delay = 2 ** attempt

        if response is not None and response.status_code == 429:
            retry_after = response.headers.get("Retry-After")

            if retry_after is not None:
                try:
                    delay = max(delay, int(retry_after))
                except ValueError:
                    pass

        sleep(delay)

    raise RuntimeError("Не вдалося отримати сторінку")

def fetch_pages(
    session: requests.Session,
    base_url: str,
    api_key: str,
    student_id: str,
    params: dict,
    raw_dir: Path,
    request_fn: Callable | None = None
) -> dict[str, Any]:

    request_fn = request_fn or request_page

    events = []
    page_count = 0
    total_count = None
    cursor = None
    seen_cursors = set()

    while True:
        request_params = dict(params)

        if cursor is not None:
            request_params["cursor"] = cursor

        response = request_fn(
            session,
            base_url.rstrip("/") + "/api/v1/delivery-events",
            params=request_params,
            headers={"X-API-Key": api_key}
        )

        page_count += 1

        save_response(
            response,
            raw_dir,
            page_count,
            request_params
        )

        try:
            body = response.json()
        except ValueError as error:
            raise ValueError(
                "Некоректний JSON API"
            ) from error

        if not isinstance(body, dict):
            raise ValueError(
                "Відповідь API має бути об'єктом"
            )

        if body.get("student_id") != student_id:
            raise ValueError("Неправильний student_id")

        if type(body.get("schema_version")) is not int or body["schema_version"] not in (1, 2):
            raise ValueError("Неправильна schema_version")

        data = body.get("data")
        count = body.get("count")
        current_total = body.get("total_count")

        if not isinstance(data, list):
            raise ValueError("Поле data має бути списком")

        if not all(isinstance(item, dict) for item in data):
            raise ValueError("Некоректна структура подій")
        for item in data:
            event_id = item.get("event_id")

            if not isinstance(event_id, str) or not event_id:
                raise ValueError("Некоректний event_id")

        if type(count) is not int or count != len(data):
            raise ValueError("Неправильний count")

        if type(current_total) is not int or current_total < 0:
            raise ValueError("Некоректний total_count")

        if total_count is None:
            total_count = current_total
        elif current_total != total_count:
            raise ValueError(
                "total_count змінився між сторінками"
            )

        events.extend(data)

        next_cursor = body.get("next_cursor")

        if next_cursor is None:
            break

        if not isinstance(next_cursor, str) or not next_cursor:
            raise ValueError("Некоректний next_cursor")

        if next_cursor in seen_cursors:
            raise ValueError("Повторення курсора")

        seen_cursors.add(next_cursor)
        cursor = next_cursor

    if len(events) != total_count:
        raise ValueError(
            "Кількість подій не збігається з total_count"
        )

    return {
        "events": events,
        "page_count": page_count,
        "total_count": total_count
    }
