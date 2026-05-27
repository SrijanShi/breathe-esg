"""
Concur Travel CSV parser (SAP Concur standard expense report export).

Concur is used by ~95M people across 46,000+ organizations. The standard
expense report export from Concur Analytics produces a predictable column set.
Covers Scope 3 Category 6 (business travel): air, rail, hotel.

Key challenge: Distance is sometimes pre-populated by Concur's mileage calculator
and sometimes blank. We use haversine fallback with a static IATA airport/city
lat-lon table for the top-200 busiest city pairs.

Reference: SAP Concur Expense Reporting documentation
"""
import csv
import io
import math
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from .base_parser import BaseParser, ParsedRow

# IATA airport code → (lat, lon) for top-100 airports by passenger volume
CITY_COORDS: dict[str, tuple[float, float]] = {
    "ATL": (33.6407, -84.4277), "LAX": (33.9425, -118.4081), "ORD": (41.9742, -87.9073),
    "DFW": (32.8998, -97.0403), "DEN": (39.8561, -104.6737), "JFK": (40.6413, -73.7781),
    "SFO": (37.6213, -122.3790), "SEA": (47.4502, -122.3088), "LAS": (36.0840, -115.1537),
    "MCO": (28.4294, -81.3089), "EWR": (40.6895, -74.1745), "MIA": (25.7959, -80.2870),
    "PHX": (33.4373, -112.0078), "IAH": (29.9902, -95.3368), "BOS": (42.3656, -71.0096),
    "MSP": (44.8848, -93.2223), "DTW": (42.2162, -83.3554), "FLL": (26.0726, -80.1527),
    "PHL": (39.8719, -75.2411), "LGA": (40.7769, -73.8740), "BWI": (39.1754, -76.6682),
    "IAD": (38.9531, -77.4565), "DCA": (38.8512, -77.0402), "MDW": (41.7868, -87.7522),
    "SLC": (40.7884, -111.9778), "SAN": (32.7338, -117.1933), "TPA": (27.9755, -82.5332),
    "DAL": (32.8471, -96.8518), "PDX": (45.5898, -122.5951), "STL": (38.7487, -90.3700),
    "HNL": (21.3245, -157.9251), "BNA": (36.1245, -86.6782), "AUS": (30.1975, -97.6664),
    "MSY": (29.9934, -90.2580), "OAK": (37.7213, -122.2208), "RSW": (26.5362, -81.7552),
    "RDU": (35.8801, -78.7880), "MCI": (39.2976, -94.7139), "SMF": (38.6954, -121.5908),
    "SJC": (37.3626, -121.9290), "CLE": (41.4117, -81.8498), "PIT": (40.4915, -80.2329),
    # International
    "LHR": (51.4775, -0.4614), "CDG": (49.0097, 2.5478), "FRA": (50.0379, 8.5622),
    "AMS": (52.3086, 4.7639), "MAD": (40.4983, -3.5676), "BCN": (41.2974, 2.0833),
    "FCO": (41.8003, 12.2389), "MUC": (48.3538, 11.7861), "ZRH": (47.4647, 8.5492),
    "VIE": (48.1103, 16.5697), "CPH": (55.6180, 12.6508), "OSL": (60.2017, 11.0838),
    "ARN": (59.6519, 17.9186), "HEL": (60.3172, 24.9633), "BRU": (50.9010, 4.4844),
    "DUB": (53.4213, -6.2701), "MAN": (53.3537, -2.2750), "LGW": (51.1537, -0.1821),
    "DXB": (25.2532, 55.3657), "SIN": (1.3644, 103.9915), "HKG": (22.3080, 113.9185),
    "NRT": (35.7720, 140.3929), "ICN": (37.4602, 126.4407), "PEK": (40.0725, 116.5975),
    "PVG": (31.1443, 121.8083), "BOM": (19.0896, 72.8656), "DEL": (28.5665, 77.1031),
    "SYD": (-33.9399, 151.1753), "MEL": (-37.6690, 144.8410), "GRU": (-23.4356, -46.4731),
    "BOG": (4.7016, -74.1469), "SCL": (-33.3930, -70.7858), "MEX": (19.4361, -99.0719),
    "YYZ": (43.6777, -79.6248), "YVR": (49.1967, -123.1815), "YUL": (45.4706, -73.7408),
    "JNB": (-26.1367, 28.2411), "NBO": (-1.3192, 36.9275), "CAI": (30.1219, 31.4056),
    "IST": (40.9769, 28.8146), "TLV": (32.0114, 34.8867), "DOH": (25.2600, 51.6138),
    "AUH": (24.4330, 54.6511), "KUL": (2.7456, 101.7099), "BKK": (13.6900, 100.7501),
    "MNL": (14.5086, 121.0194), "CGK": (-6.1256, 106.6559), "FCO": (41.8003, 12.2389),
    # Common city codes (3-letter city codes used in Concur when airport code missing)
    "NYC": (40.7128, -74.0060), "LON": (51.5074, -0.1278), "PAR": (48.8566, 2.3522),
    "CHI": (41.8781, -87.6298), "SFR": (37.7749, -122.4194), "LAG": (6.5244, 3.3792),
    "BER": (52.5200, 13.4050), "ROM": (41.9028, 12.4964), "TOK": (35.6762, 139.6503),
    "SHA": (31.2304, 121.4737), "BEI": (39.9042, 116.4074), "MUM": (19.0760, 72.8777),
    "CHL": (28.7041, 77.1025), "SAO": (-23.5505, -46.6333), "BJG": (-26.2041, 28.0473),
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _city_distance_km(origin: str, destination: str) -> float | None:
    o = origin.strip().upper()[:3]
    d = destination.strip().upper()[:3]
    if o in CITY_COORDS and d in CITY_COORDS:
        lat1, lon1 = CITY_COORDS[o]
        lat2, lon2 = CITY_COORDS[d]
        return _haversine_km(lat1, lon1, lat2, lon2)
    return None


def _parse_date(value: str) -> date | None:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d.%m.%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


# Concur expense type strings → internal category + scope 3 activity category
EXPENSE_TYPE_MAP: dict[str, tuple[str, str]] = {
    "airfare": ("flight", "flight_km_economy"),
    "air": ("flight", "flight_km_economy"),
    "flight": ("flight", "flight_km_economy"),
    "airline": ("flight", "flight_km_economy"),
    "hotel": ("hotel", "hotel_night"),
    "lodging": ("hotel", "hotel_night"),
    "accommodation": ("hotel", "hotel_night"),
    "rail": ("rail", "rail_km"),
    "train": ("rail", "rail_km"),
    "eurostar": ("rail", "rail_km"),
    "amtrak": ("rail", "rail_km"),
    "bus": ("ground", "rail_km"),  # use rail factor as approximation
    "taxi": ("ground", "rail_km"),
    "car": ("ground", "rail_km"),
    "car rental": ("ground", "rail_km"),
}

# Flight class → activity category override
FLIGHT_CLASS_MAP: dict[str, str] = {
    "business": "flight_km_business",
    "business class": "flight_km_business",
    "first": "flight_km_first",
    "first class": "flight_km_first",
    "economy": "flight_km_economy",
    "economy class": "flight_km_economy",
    "premium economy": "flight_km_economy",
}

COL_ALIASES: dict[str, str] = {
    "REPORT ID": "report_id",
    "REPORT NAME": "report_name",
    "TRANSACTION DATE": "transaction_date",
    "EXPENSE DATE": "transaction_date",
    "DATE": "transaction_date",
    "EXPENSE TYPE": "expense_type",
    "MERCHANT NAME": "vendor",
    "MERCHANT": "vendor",
    "AMOUNT": "amount",
    "TOTAL": "amount",
    "CURRENCY": "currency",
    "ORIGIN CITY": "origin",
    "ORIGIN": "origin",
    "FROM": "origin",
    "DESTINATION CITY": "destination",
    "DESTINATION": "destination",
    "TO": "destination",
    "MILES/KM": "distance",
    "DISTANCE": "distance",
    "MILES": "distance",
    "KM": "distance",
    "DISTANCE UNIT": "distance_unit",
    "CLASS": "travel_class",
    "CABIN CLASS": "travel_class",
    "NIGHTS": "nights",
    "EMPLOYEE ID": "employee_id",
    "EMPLOYEE": "employee_id",
    "COST CENTER": "department",
}


class TravelCsvParser(BaseParser):
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

            # Date
            date_raw = row.get("transaction_date", "")
            parsed_date = _parse_date(date_raw) if date_raw else None
            if not parsed_date:
                parsed.add_error("transaction_date", f"Cannot parse date: '{date_raw}'")
            else:
                parsed.data["activity_date"] = parsed_date.isoformat()

            # Expense type → category mapping
            expense_raw = row.get("expense_type", "").lower().strip()
            category_key, activity_cat = EXPENSE_TYPE_MAP.get(
                expense_raw, ("unknown", "flight_km_economy")
            )
            if category_key == "unknown":
                parsed.add_warning("expense_type", f"Unknown expense type: '{expense_raw}'")

            # Flight class override
            travel_class = row.get("travel_class", "").lower().strip()
            if category_key == "flight" and travel_class in FLIGHT_CLASS_MAP:
                activity_cat = FLIGHT_CLASS_MAP[travel_class]

            parsed.data["activity_category"] = activity_cat
            parsed.data["scope"] = 3
            parsed.data["expense_category"] = category_key

            # Quantity/distance calculation
            if category_key == "hotel":
                nights_raw = row.get("nights", "1")
                try:
                    nights = Decimal(nights_raw) if nights_raw else Decimal("1")
                except InvalidOperation:
                    nights = Decimal("1")
                    parsed.add_warning("nights", f"Cannot parse nights: '{nights_raw}', defaulting to 1")
                parsed.data["raw_quantity"] = str(nights)
                parsed.data["raw_unit"] = "night"
                parsed.data["normalized_quantity"] = str(nights)
                parsed.data["normalized_unit"] = "night"

            elif category_key in ("flight", "rail", "ground"):
                dist_raw = row.get("distance", "")
                dist_unit = row.get("distance_unit", "km").lower().strip()

                if dist_raw:
                    try:
                        dist = Decimal(dist_raw.replace(",", ""))
                    except InvalidOperation:
                        dist = None
                        parsed.add_warning("distance", f"Cannot parse distance: '{dist_raw}'")
                else:
                    dist = None

                # Convert miles to km if needed
                if dist is not None and dist_unit in ("mile", "miles", "mi"):
                    dist = dist * Decimal("1.60934")
                    dist_unit = "km"

                # Haversine fallback
                if dist is None or dist == Decimal("0"):
                    origin = row.get("origin", "")
                    destination = row.get("destination", "")
                    calc_dist = _city_distance_km(origin, destination)
                    if calc_dist:
                        dist = Decimal(str(round(calc_dist, 2)))
                        parsed.add_warning("distance", f"Distance estimated via haversine from {origin}→{destination}: {dist} km")
                    else:
                        parsed.add_error("distance", f"No distance and cannot estimate from '{origin}'→'{destination}'")
                        dist = Decimal("0")

                parsed.data["raw_quantity"] = str(dist)
                parsed.data["raw_unit"] = "km"
                parsed.data["normalized_quantity"] = str(dist)
                parsed.data["normalized_unit"] = "km"
            else:
                # Fallback: use amount as proxy
                amount_raw = row.get("amount", "0")
                try:
                    amount = Decimal(amount_raw.replace(",", ""))
                except InvalidOperation:
                    amount = Decimal("0")
                parsed.data["raw_quantity"] = str(amount)
                parsed.data["raw_unit"] = row.get("currency", "USD")
                parsed.data["normalized_quantity"] = str(amount)
                parsed.data["normalized_unit"] = "usd"

            parsed.data["vendor"] = row.get("vendor", "")
            parsed.data["location"] = f"{row.get('origin', '')}→{row.get('destination', '')}".strip("→")
            parsed.data["department"] = row.get("department", "")
            parsed.data["description"] = f"{row.get('expense_type', '')} — {row.get('report_name', '')}"
            parsed.data["raw_currency"] = row.get("currency", "")
            parsed.data["_raw"] = dict(row)

            rows.append(parsed)

        return rows
