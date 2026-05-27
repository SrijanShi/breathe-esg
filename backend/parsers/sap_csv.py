"""
SAP flat-file CSV parser (ME2N / MIRO procurement export format).

Real SAP exports use DD.MM.YYYY dates, SAP internal unit codes (L, KG, KWH),
and German field names in some locale configurations. We handle both German
and English column aliases to support common SAP configurations.
"""
import csv
import io
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from .base_parser import BaseParser, ParsedRow

# SAP exports in German locale use these column names; English locale may differ.
# We map both variants → a canonical internal name.
COLUMN_ALIASES: dict[str, str] = {
    # German → canonical
    "BUKRS": "company_code",
    "BLDAT": "activity_date",
    "BUDAT": "posting_date",
    "MATNR": "material_number",
    "MATKL": "material_group",
    "TXZ01": "description",
    "MENGE": "raw_quantity",
    "MEINS": "raw_unit",
    "NETWR": "net_value",
    "WAERS": "currency",
    "WERKS": "location",
    "LIFNR": "vendor_id",
    "NAME1": "vendor_name",
    "KOSTL": "department",
    # English column names sometimes used in custom ABAP reports
    "Company Code": "company_code",
    "Document Date": "activity_date",
    "Posting Date": "posting_date",
    "Material": "material_number",
    "Material Group": "material_group",
    "Description": "description",
    "Quantity": "raw_quantity",
    "Unit": "raw_unit",
    "Net Value": "net_value",
    "Currency": "currency",
    "Plant": "location",
    "Vendor": "vendor_id",
    "Vendor Name": "vendor_name",
    "Cost Center": "department",
}

# SAP internal unit → (canonical unit name, multiplier to canonical)
UNIT_NORMALIZATIONS: dict[str, tuple[str, float]] = {
    "L": ("litre", 1.0),
    "LTR": ("litre", 1.0),
    "GL": ("litre", 3.785),        # US gallon → litres
    "GAL": ("litre", 3.785),
    "KG": ("kg", 1.0),
    "G": ("kg", 0.001),
    "MT": ("kg", 1000.0),          # metric tonne → kg
    "T": ("kg", 1000.0),
    "KWH": ("kwh", 1.0),
    "MWH": ("kwh", 1000.0),
    "GJ": ("kwh", 277.778),        # GigaJoule → kWh
    "M3": ("m3", 1.0),             # cubic metres (natural gas)
    "CF": ("m3", 0.0283168),       # cubic feet → m3
    "PC": ("piece", 1.0),
    "ST": ("piece", 1.0),          # SAP "Stück" (piece)
}

# Material groups / material number prefixes that classify as Scope 1 (direct combustion)
SCOPE_1_MATERIAL_GROUPS = {"ENER", "FUEL", "GAS", "OIL"}
SCOPE_1_MATERIAL_PREFIXES = ("FUEL-", "NAT-GAS-", "DIESEL-", "PETROL-", "LPG-", "COAL-", "HFO-")

# Material groups that classify as Scope 2 (purchased electricity)
SCOPE_2_MATERIAL_GROUPS = {"ELEC", "UTIL", "POWER"}
SCOPE_2_MATERIAL_PREFIXES = ("ELEC-", "ELECTRICITY-")


def _classify_scope(material_group: str, material_number: str) -> int:
    mg = material_group.upper().strip()
    mn = material_number.upper().strip()
    if mg in SCOPE_1_MATERIAL_GROUPS or any(mn.startswith(p) for p in SCOPE_1_MATERIAL_PREFIXES):
        return 1
    if mg in SCOPE_2_MATERIAL_GROUPS or any(mn.startswith(p) for p in SCOPE_2_MATERIAL_PREFIXES):
        return 2
    return 3


def _parse_sap_date(value: str) -> date | None:
    """Handle DD.MM.YYYY (SAP default) and YYYY-MM-DD (ISO)."""
    value = value.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_unit(raw_unit: str) -> tuple[str, float]:
    """Return (canonical_unit, multiplier). Returns raw_unit with 1.0 if unknown."""
    key = raw_unit.upper().strip()
    return UNIT_NORMALIZATIONS.get(key, (raw_unit.lower(), 1.0))


class SAPCsvParser(BaseParser):
    def parse(self, file_bytes: bytes) -> list[ParsedRow]:
        # Detect encoding — SAP exports are often latin-1 or utf-8-sig
        for encoding in ("utf-8-sig", "latin-1", "utf-8"):
            try:
                text = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = file_bytes.decode("latin-1", errors="replace")

        reader = csv.DictReader(io.StringIO(text))
        rows: list[ParsedRow] = []

        for i, raw_row in enumerate(reader, start=2):  # 1-based, row 1 is header
            # Normalize column names via alias map
            row = {}
            for col, val in raw_row.items():
                canonical = COLUMN_ALIASES.get(col.strip(), col.strip().lower())
                row[canonical] = (val or "").strip()

            parsed = ParsedRow(row_number=i, data={})

            # Skip completely empty rows
            if not any(row.values()):
                parsed.status = "skipped"
                rows.append(parsed)
                continue

            # Activity date
            date_raw = row.get("activity_date", "")
            parsed_date = _parse_sap_date(date_raw) if date_raw else None
            if not parsed_date:
                parsed.add_error("activity_date", f"Cannot parse date: '{date_raw}'")
            else:
                parsed.data["activity_date"] = parsed_date.isoformat()

            # Quantity
            qty_raw = row.get("raw_quantity", "").replace(",", ".")
            try:
                qty = Decimal(qty_raw)
                parsed.data["raw_quantity"] = str(qty)
            except (InvalidOperation, ValueError):
                parsed.add_error("raw_quantity", f"Cannot parse quantity: '{qty_raw}'")
                qty = Decimal("0")

            # Unit
            unit_raw = row.get("raw_unit", "").upper().strip()
            if not unit_raw:
                parsed.add_warning("raw_unit", "No unit specified")
                unit_raw = "???"
            canonical_unit, multiplier = _normalize_unit(unit_raw)
            parsed.data["raw_unit"] = unit_raw
            parsed.data["normalized_unit"] = canonical_unit
            parsed.data["unit_multiplier"] = multiplier
            parsed.data["normalized_quantity"] = str(qty * Decimal(str(multiplier)))

            # Scope classification
            mat_grp = row.get("material_group", "")
            mat_num = row.get("material_number", "")
            parsed.data["scope"] = _classify_scope(mat_grp, mat_num)

            # Activity category derived from material group + scope
            if parsed.data.get("scope") == 1:
                if "GAS" in mat_grp.upper() or "GAS" in mat_num.upper():
                    parsed.data["activity_category"] = "natural_gas_kwh"
                elif "DIESEL" in mat_num.upper():
                    parsed.data["activity_category"] = "diesel_litre"
                elif "LPG" in mat_num.upper():
                    parsed.data["activity_category"] = "lpg_litre"
                else:
                    parsed.data["activity_category"] = "petrol_litre"
            elif parsed.data.get("scope") == 2:
                parsed.data["activity_category"] = "electricity_kwh_us_average"
            else:
                parsed.data["activity_category"] = "procurement_usd_general"

            # Remaining fields
            parsed.data["vendor"] = row.get("vendor_name") or row.get("vendor_id", "")
            parsed.data["location"] = row.get("location", "")
            parsed.data["department"] = row.get("department", "")
            parsed.data["description"] = row.get("description", "")
            parsed.data["raw_currency"] = row.get("currency", "")
            parsed.data["source_reference"] = row.get("material_number", "")

            # Store full raw row for traceability
            parsed.data["_raw"] = dict(row)

            rows.append(parsed)

        return rows
