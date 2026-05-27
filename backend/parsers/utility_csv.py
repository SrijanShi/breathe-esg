"""
Utility portal CSV parser — Green Button Alliance ESPI format.

Green Button is an open standard adopted by major US utilities (PG&E, Con Edison,
National Grid, etc.) and many EU equivalents. The CSV variant is the most common
download from utility account portals. Daily granularity is the norm for smart meter
accounts; older accounts may export monthly.

Reference: https://www.greenbuttonalliance.org
"""
import csv
import io
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from .base_parser import BaseParser, ParsedRow

# Green Button CSV standard columns
REQUIRED_COLS = {"DATE", "CONSUMPTION", "UNITS"}

# Some portals use slight variations
COL_ALIASES: dict[str, str] = {
    "DATE": "date",
    "START DATE": "date",
    "START TIME": "start_time",
    "END TIME": "end_time",
    "CONSUMPTION": "consumption",
    "USAGE": "consumption",
    "KWH": "consumption",
    "UNITS": "units",
    "UNIT": "units",
    "TYPE": "record_type",
    "NOTES": "notes",
    "COST": "cost",
    "TOTAL COST": "cost",
    "METER NUMBER": "meter_number",
    "METER": "meter_number",
    "SERVICE ADDRESS": "service_address",
    "ACCOUNT NUMBER": "account_number",
}

VALID_UNITS = {"kwh", "kwH", "kWh", "KWH", "mwh", "MWH", "wh", "WH"}


def _parse_date(value: str) -> date | None:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y"):
        try:
            return datetime.strptime(value.split("T")[0], fmt.split("T")[0]).date()
        except ValueError:
            continue
    return None


def _normalize_consumption(value: str, unit: str) -> tuple[Decimal, str]:
    """Convert to kWh. Returns (kwh_value, 'kwh')."""
    try:
        qty = Decimal(value.replace(",", "."))
    except InvalidOperation:
        return Decimal("0"), "kwh"

    unit_clean = unit.strip().lower()
    if unit_clean in ("mwh",):
        return qty * Decimal("1000"), "kwh"
    elif unit_clean in ("wh",):
        return qty / Decimal("1000"), "kwh"
    return qty, "kwh"


def _is_summary_row(row: dict) -> bool:
    """Detect monthly/annual summary rows that duplicate interval data."""
    record_type = row.get("record_type", "").lower()
    notes = row.get("notes", "").lower()
    return "monthly total" in notes or "annual total" in notes or "summary" in record_type


class UtilityCsvParser(BaseParser):
    def parse(self, file_bytes: bytes) -> list[ParsedRow]:
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                text = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = file_bytes.decode("latin-1", errors="replace")

        reader = csv.DictReader(io.StringIO(text))
        rows: list[ParsedRow] = []

        for i, raw_row in enumerate(reader, start=2):
            row = {}
            for col, val in raw_row.items():
                canonical = COL_ALIASES.get((col or "").strip().upper(), (col or "").strip().lower())
                row[canonical] = (val or "").strip()

            parsed = ParsedRow(row_number=i, data={})

            if not any(row.values()):
                parsed.status = "skipped"
                rows.append(parsed)
                continue

            if _is_summary_row(row):
                parsed.status = "skipped"
                parsed.data["skip_reason"] = "summary_row"
                rows.append(parsed)
                continue

            # Date
            date_raw = row.get("date", "")
            parsed_date = _parse_date(date_raw) if date_raw else None
            if not parsed_date:
                parsed.add_error("date", f"Cannot parse date: '{date_raw}'")
            else:
                parsed.data["activity_date"] = parsed_date.isoformat()

            # Consumption
            consumption_raw = row.get("consumption", "")
            unit_raw = row.get("units", "kWh")
            if not consumption_raw:
                parsed.add_error("consumption", "Missing consumption value")
            else:
                kwh_val, norm_unit = _normalize_consumption(consumption_raw, unit_raw)
                parsed.data["raw_quantity"] = consumption_raw
                parsed.data["raw_unit"] = unit_raw
                parsed.data["normalized_quantity"] = str(kwh_val)
                parsed.data["normalized_unit"] = norm_unit

            parsed.data["scope"] = 2
            parsed.data["activity_category"] = "electricity_kwh_us_average"
            parsed.data["raw_currency"] = ""
            parsed.data["vendor"] = ""
            parsed.data["location"] = row.get("service_address", "") or row.get("meter_number", "")
            parsed.data["description"] = f"Electricity usage — {row.get('record_type', 'Electric usage')}"
            parsed.data["_raw"] = dict(row)

            rows.append(parsed)

        return rows
