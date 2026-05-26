"""
Emission factor seed data.

Sources:
- DEFRA 2023 GHG Conversion Factors for Company Reporting
  https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting
- EPA eGRID 2022 (US electricity grid subregion averages)
  https://www.epa.gov/egrid
- EPA USEEIO v2.0 (spend-based Scope 3)
  https://www.epa.gov/land-research/us-environmentally-extended-input-output-useeio-technical-content
"""
from datetime import date

# Each entry: (activity_category, scope, kg_co2e_per_unit, unit, source, valid_from, notes)
SEED_FACTORS = [
    # ── Scope 1: Direct combustion (DEFRA 2023) ──────────────────────────────
    (
        "diesel_litre", 1, "2.53100000", "litre", "defra",
        date(2023, 1, 1), "DEFRA 2023 — Diesel (average biofuel blend)",
    ),
    (
        "natural_gas_kwh", 1, "0.18290000", "kwh", "defra",
        date(2023, 1, 1), "DEFRA 2023 — Natural gas combustion per kWh",
    ),
    (
        "lpg_litre", 1, "1.55510000", "litre", "defra",
        date(2023, 1, 1), "DEFRA 2023 — LPG",
    ),
    (
        "petrol_litre", 1, "2.31200000", "litre", "defra",
        date(2023, 1, 1), "DEFRA 2023 — Petrol (average biofuel blend)",
    ),
    (
        "hfo_litre", 1, "2.77300000", "litre", "defra",
        date(2023, 1, 1), "DEFRA 2023 — Heavy fuel oil",
    ),
    (
        "natural_gas_m3", 1, "1.92200000", "m3", "defra",
        date(2023, 1, 1), "DEFRA 2023 — Natural gas per m3 (approx. 10.5 kWh/m3)",
    ),
    # ── Scope 2: Purchased electricity (EPA eGRID 2022) ──────────────────────
    (
        "electricity_kwh_us_average", 2, "0.38600000", "kwh", "epa_egrid",
        date(2022, 1, 1), "EPA eGRID 2022 — US national average",
    ),
    (
        "electricity_kwh_rfcw", 2, "0.44200000", "kwh", "epa_egrid",
        date(2022, 1, 1), "EPA eGRID 2022 — RFC West (Ohio, Indiana, Michigan region)",
    ),
    (
        "electricity_kwh_rfce", 2, "0.29400000", "kwh", "epa_egrid",
        date(2022, 1, 1), "EPA eGRID 2022 — RFC East (Pennsylvania, NJ, MD region)",
    ),
    (
        "electricity_kwh_wecc_ca", 2, "0.21000000", "kwh", "epa_egrid",
        date(2022, 1, 1), "EPA eGRID 2022 — WECC California (high renewable penetration)",
    ),
    (
        "electricity_kwh_mroe", 2, "0.50200000", "kwh", "epa_egrid",
        date(2022, 1, 1), "EPA eGRID 2022 — MRO East (Wisconsin, Minnesota region)",
    ),
    (
        "electricity_kwh_uk", 2, "0.20700000", "kwh", "defra",
        date(2023, 1, 1), "DEFRA 2023 — UK national grid (location-based)",
    ),
    (
        "electricity_kwh_eu_average", 2, "0.27600000", "kwh", "iea",
        date(2022, 1, 1), "IEA 2022 — EU27 average grid intensity",
    ),
    # ── Scope 3 Cat 6: Business travel (DEFRA 2023) ───────────────────────────
    (
        "flight_km_economy", 3, "0.25550000", "km", "defra",
        date(2023, 1, 1), "DEFRA 2023 — Short/long haul average economy, including RFI factor 1.9",
    ),
    (
        "flight_km_business", 3, "0.51100000", "km", "defra",
        date(2023, 1, 1), "DEFRA 2023 — Business class (2× economy seat area factor)",
    ),
    (
        "flight_km_first", 3, "0.61320000", "km", "defra",
        date(2023, 1, 1), "DEFRA 2023 — First class (2.4× economy seat area factor)",
    ),
    (
        "rail_km", 3, "0.03700000", "km", "defra",
        date(2023, 1, 1), "DEFRA 2023 — National rail (UK average); used as proxy for international rail",
    ),
    (
        "hotel_night", 3, "31.40000000", "night", "defra",
        date(2023, 1, 1), "DEFRA 2023 — Hotel stay per night (UK average, all categories)",
    ),
    # ── Scope 3 Cat 1: Purchased goods/services (EPA USEEIO spend-based) ─────
    (
        "procurement_usd_general", 3, "0.44000000", "usd", "epa_useeio",
        date(2022, 1, 1), "EPA USEEIO v2.0 — Average supply chain intensity across all sectors",
    ),
]
