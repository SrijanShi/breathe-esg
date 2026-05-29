# Emission Factor Sources

All emission factors seeded in the database are from publicly available, peer-reviewed sources. The `factor_source` field on each `EmissionFactor` record identifies the originating dataset.

---

## DEFRA (UK Department for Environment, Food & Rural Affairs)

**Source:** [Greenhouse gas reporting: conversion factors 2023](https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting)

**Used for:**
- Scope 1: diesel combustion (2.531 kgCO₂e/litre), natural gas (0.18293 kgCO₂e/kWh), LPG (1.5551 kgCO₂e/litre), petrol (2.312 kgCO₂e/litre)
- Scope 3 business travel: flight economy (0.2555 kgCO₂e/km), business class (0.511 kgCO₂e/km), first class (0.6132 kgCO₂e/km), rail (0.03694 kgCO₂e/km), hotel stays (31.4 kgCO₂e/night)

**Why DEFRA:** The DEFRA conversion factors are updated annually, cover all major activity categories, and are widely accepted by corporate GHG reporters globally. They are the standard source used by most UK-headquartered companies and are accepted by CDP, SBTi, and the GHG Protocol for international reporting.

**Vintage:** 2023 factors (valid from 2023-01-01, no end date in the seed data — treated as currently applicable).

---

## EPA eGRID (US Environmental Protection Agency)

**Source:** [eGRID 2022 Summary Tables](https://www.epa.gov/egrid/download-data)

**Used for:**
- Scope 2 electricity: US average (0.386 kgCO₂e/kWh), RFCW (0.442 kgCO₂e/kWh), WECC-CA (0.210 kgCO₂e/kWh), NPCC-NYC (0.267 kgCO₂e/kWh)

**Why eGRID:** eGRID is the authoritative source for US regional electricity emission factors. It is published by the EPA and is the required source for US GHG Protocol Scope 2 reporting. The RFCW subregion (RFC West, covering Ohio/Indiana/Michigan) and WECC-CA (California) are the two most common factors for manufacturing and technology companies respectively.

**Vintage:** eGRID 2022 (published November 2023, valid from 2022-01-01).

---

## IEA (International Energy Agency)

**Source:** [Emission Factors 2023](https://www.iea.org/data-and-statistics/data-product/emissions-factors-2023)

**Used for:**
- Scope 2 electricity: UK grid (0.207 kgCO₂e/kWh), EU average (0.276 kgCO₂e/kWh)

**Why IEA:** For non-US electricity consumption, IEA provides country-level emission factors that are accepted by the GHG Protocol and CDP. The UK grid factor has declined significantly as renewable penetration has increased; the 2023 IEA figure reflects this.

**Vintage:** IEA 2023 (valid from 2023-01-01).

---

## ICAO (International Civil Aviation Organization)

**Source:** [ICAO Carbon Emissions Calculator Methodology, Version 12](https://www.icao.int/environmental-protection/CarbonOffset/Documents/Methodology%20ICAO%20Carbon%20Calculator_v12-2023.pdf)

**Used for:** Cross-checking flight emission factors. The ICAO methodology is used as a secondary validation for the DEFRA flight factors.

**Note:** The DEFRA flight factors are used in the database (not ICAO directly), but the ICAO methodology informs the class multipliers applied in the travel parser (Economy 1.0×, Business 2.0×, First 2.4×). These multipliers are consistent with both DEFRA 2023 and the ICAO methodology.

---

## Unit Normalization References

The SAP parser normalizes non-SI units using the following references:

| SAP MEINS Code | Conversion | Reference |
|---|---|---|
| `GL` (US gallon) | × 3.78541 → litres | NIST Handbook 44 |
| `MT` (metric ton) | × 1000 → kg | SI definition |
| `MWH` (megawatt-hour) | × 1000 → kWh | SI definition |
| `GJ` (gigajoule) | × 277.778 → kWh | IEA energy unit conversion |
| `M3` (cubic metre) | as-is for gas; × 10.55 → kWh calorific for natural gas | Ofgem standard calorific value |

---

## Haversine Distance Calculation

The travel parser uses haversine great-circle distance as a fallback when Concur does not provide a `Distance` value. Airport coordinates are sourced from:

**Source:** [OpenFlights Airport Database](https://openflights.org/data.html) — coordinates for IATA airport codes, public domain.

The top-100 airports by annual passenger volume are included in the static lookup table in `parsers/travel_csv.py`.
