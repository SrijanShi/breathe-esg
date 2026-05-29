# Breathe ESG — Emissions Ingestion and Review Platform

A Django REST + React prototype that ingests carbon emissions data from three enterprise sources, normalises it to kg CO₂e, and surfaces an analyst review workflow before records are locked for audit.

---

## Live Deployment

| Service | URL |
|---------|-----|
| Frontend | https://frontend-ochre-chi-32.vercel.app |
| Backend API | https://breathe-esg-api.fly.dev |

**Demo credentials**

| Role | Email | Password |
|------|-------|----------|
| Analyst | analyst@breatheesg.com | Analyst123! |
| Admin | admin@breatheesg.com | Admin123! |
| Auditor | auditor@breatheesg.com | Auditor123! |

---

## What It Does

1. **Upload** — drag-and-drop CSV files from SAP, utility portals, or Concur into the Ingestion page. The parser runs synchronously and reports row-level errors immediately.
2. **Review** — the Review Queue shows every parsed emission record with its scope badge, suspicion flags, and review status. Filter by scope, source, status, date, or suspicious flag. Click any row for the full provenance chain (source file → raw row → normalised value → emission factor).
3. **Approve / Reject / Flag** — analysts approve or reject records with optional notes. Suspicious rows (3σ outlier, stale date, zero quantity, duplicate) are pre-flagged amber.
4. **Lock** — admins lock approved records, after which no edits are permitted. Every state change is written to an immutable audit log.
5. **Audit Trail** — the Audit page shows the full org-wide action history, filterable by action type.

---

## Three Data Sources

### SAP Procurement (Scope 1 / 2 / 3)
Format: ME2N / MIRO flat-file CSV with German column headers (BUKRS, BLDAT, MATNR, MENGE, MEINS, WERKS, LIFNR, KOSTL). Dates in DD.MM.YYYY. MEINS unit codes normalised: GL→L, MT→kg×1000, MWH→kWh×1000, GJ→kWh×277.778.

Scope assigned by MATKL material group: FUEL/GAS→Scope 1, ELEC/UTIL→Scope 2, all others→Scope 3.

### Utility Electricity (Scope 2)
Format: Green Button Alliance portal CSV (TYPE, DATE, START TIME, END TIME, CONSUMPTION, UNITS, NOTES). Daily interval readings. Monthly summary rows are detected and skipped. Mixed-case unit normalisation (kWH→kWh).

### Corporate Travel (Scope 3)
Format: Concur standard expense report CSV (Report ID, Transaction Date, Expense Type, Merchant Name, Amount, Currency, Origin City, Destination City, Distance, Distance Unit, Class, Nights, Employee ID). Haversine fallback for blank Distance fields using a 100-city IATA coordinate table. Class multipliers: Economy 1.0×, Business 2.0×, First 2.4× (DEFRA 2023). Hotels at 31.4 kgCO₂e/night.

---

## Emission Factors

All factors from DEFRA 2023 and EPA eGRID 2022. Seeded into the database on first deploy via `python manage.py seed_factors`. The `EmissionFactor` model stores source, validity window, and unit so any factor can be updated without touching records that already used it.

---

## Local Development

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # set SECRET_KEY and DATABASE_URL
python manage.py migrate
python manage.py seed_factors
python manage.py create_demo  # creates demo org + users
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
# For local dev, the Vite proxy forwards /api → http://localhost:8000
npm run dev
```

Visit http://localhost:5173. Log in with `analyst@breatheesg.com / Analyst123!`.

### Sample Data

Upload the files in `sample_data/` from the Ingestion page to populate records:

| File | Source | Rows |
|------|--------|------|
| `sap_procurement.csv` | SAP ME2N/MIRO | 20 rows, 1 intentional 3σ outlier |
| `utility_electricity.csv` | Green Button Alliance | 50 daily readings, 1 HVAC spike, 1 zero-read |
| `travel_concur.csv` | Concur expense report | 35 rows, mixed economy/business/first, some blank distances |

---

## Project Structure

```
breathe-esg/
├── backend/
│   ├── config/           # Django settings (base/production), urls, wsgi
│   ├── core/             # Organization, UserProfile
│   ├── ingestion/        # IngestionBatch, RawRecord, ingestion service
│   ├── emissions/        # EmissionRecord, EmissionFactor, AuditLog, normalizer
│   ├── api/              # DRF viewsets, serializers, auth, pagination
│   ├── parsers/          # sap_csv.py, utility_csv.py, travel_csv.py
│   ├── Dockerfile
│   └── fly.toml
├── frontend/
│   └── src/
│       ├── pages/        # Login, Dashboard, Ingestion, ReviewQueue, Audit
│       ├── components/   # AppShell, review drawer, shared UI
│       ├── hooks/        # useAuth, useEmissions, useBatches, useAuditLog
│       └── api/          # typed Axios client with JWT refresh interceptor
├── sample_data/
├── MODEL.md
├── DECISIONS.md
├── TRADEOFFS.md
└── SOURCES.md
```

---

## Documentation

- [MODEL.md](MODEL.md) — data model design and multi-tenancy approach
- [DECISIONS.md](DECISIONS.md) — every ambiguity resolved with reasoning
- [TRADEOFFS.md](TRADEOFFS.md) — three deliberate cuts and why
- [SOURCES.md](SOURCES.md) — real-world format research for each source

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | Django 6, Django REST Framework, SimpleJWT (httpOnly cookies) |
| Database | PostgreSQL (Fly.io managed) |
| Auth | JWT in httpOnly cookies, CORS with credentials |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4 |
| Tables | TanStack Table v8 |
| Charts | Recharts |
| Data fetching | TanStack Query v5 with optimistic updates |
| Backend deploy | Fly.io (Singapore region) |
| Frontend deploy | Vercel |
