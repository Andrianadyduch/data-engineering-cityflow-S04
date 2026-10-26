from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

def validate_quantity(value):
    if not isinstance(value, str) or not value.isdigit():
        return False

    number = int(value)
    return 1 <= number <= 2147483647


def validate_currency(value):
    return value in ("UAH", "USD", "EUR")


def validate_amount(value):
    if not isinstance(value, str):
        return False

    try:
        number = Decimal(value)
    except InvalidOperation:
        return False

    if not number.is_finite():
        return False

    return (
        number >= 0
        and number < Decimal("10000000000")
        and number == number.quantize(Decimal("0.01"))
    )


def validate_date(value):
    if not isinstance(value, str) or not value.strip():
        return False

    try:
        normalized = value.strip().replace("Z", "+00:00")

        if "." in normalized:
            before, after = normalized.split(".", 1)
            timezone_start = max(after.find("+"), after.find("-"))

            if timezone_start != -1:
                fraction = after[:timezone_start]
                timezone_part = after[timezone_start:]
            else:
                fraction = after
                timezone_part = ""

            if fraction.isdigit() and len(fraction) > 6:
                normalized = (
                    before + "." + fraction[:6] + timezone_part
                )

        date = datetime.fromisoformat(normalized)

        return date.tzinfo is not None and date.utcoffset() is not None

    except ValueError:
        pass

    try:
        datetime.strptime(value, "%d/%m/%Y %H:%M").replace(
            tzinfo=timezone.utc
        )
        return True
    except ValueError:
        return False


def parse_date(value):
    if not validate_date(value):
        raise ValueError(f"Некоректна дата: {value}")

    normalized = value.strip().replace("Z", "+00:00")

    try:
        if "." in normalized:
            before, after = normalized.split(".", 1)
            timezone_start = max(after.find("+"), after.find("-"))

            if timezone_start != -1:
                fraction = after[:timezone_start]
                timezone_part = after[timezone_start:]
            else:
                fraction = after
                timezone_part = ""

            if fraction.isdigit() and len(fraction) > 6:
                normalized = (
                    before + "." + fraction[:6] + timezone_part
                )

        date = datetime.fromisoformat(normalized)

    except ValueError:
        date = datetime.strptime(value, "%d/%m/%Y %H:%M")
        date = date.replace(tzinfo=timezone.utc)

    return date.astimezone(timezone.utc)
