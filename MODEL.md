# Data Model

## Design Philosophy

The model is built around three invariants that matter for carbon accounting:

1. **Provenance is immutable.** Every emission figure must trace back to a raw file row, a parsed record, and an emission factor with a known source and validity window. Deleting or overwriting any link in that chain makes the data unauditable.

2. **Review state is separate from accounting data.** Whether an analyst has approved a record is orthogonal to what the record says. The two concerns live in separate fields and have separate state machines.

3. **The audit log is append-only.** Once written, an `AuditLog` row cannot be updated or deleted — `save()` raises `ValueError` if the instance already has a primary key.

---

## Entity Relationship Summary

```
Organization
  ├── UserProfile (many)
  ├── IngestionBatch (many)
  │     └── RawRecord (many)
  │           └── EmissionRecord (one)
  │                 ├── EmissionFactor (FK — nullable for custom lines)
  │                 └── AuditLog (many)
  └── EmissionFactor (org-specific overrides; global factors have org=null)
```

---

## Core Models

### Organization

Tenant root. Every queryable resource is scoped by `organization`. UUID primary key prevents enumeration.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `name` | CharField | Display name |
| `slug` | SlugField | URL-safe identifier, unique |
| `fiscal_year_start_month` | IntegerField | 1–12; default 1 (Jan). Needed for FY boundary in reports. |
| `default_electricity_grid` | CharField | EPA eGRID region code; used as Scope 2 factor lookup key |
| `created_at` | DateTimeField | |

### UserProfile (extends AbstractUser)

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `organization` | FK → Organization | null=True for superusers |
| `role` | CharField | `admin` / `analyst` / `auditor` |

Role semantics:
- **admin**: full CRUD + lock/unlock
- **analyst**: approve/reject/flag; cannot lock
- **auditor**: read-only across all records and audit log

### IngestionBatch

One row per uploaded file.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `organization` | FK | |
| `uploaded_by` | FK → UserProfile | null on delete → SET_NULL |
| `source_type` | CharField | `sap` / `utility` / `travel` |
| `original_filename` | CharField | Preserved for display |
| `file` | FileField | Stored under `ingestion/` |
| `file_sha256` | CharField(64) | Hex digest; unique per org to prevent re-upload |
| `file_size_bytes` | IntegerField | |
| `status` | CharField | `pending` → `processing` → `complete` / `failed` |
| `row_count_total` | IntegerField | Lines in file minus header |
| `row_count_parsed` | IntegerField | Successfully created EmissionRecords |
| `row_count_failed` | IntegerField | Rows that raised parse errors |
| `row_count_suspicious` | IntegerField | Parsed rows with suspicion flags |
| `parse_errors_summary` | TextField | Human-readable error digest |
| `uploaded_at` | DateTimeField | |
| `completed_at` | DateTimeField | null=True |

**Dedup logic:** `(organization, file_sha256)` is effectively unique — the API returns `HTTP 409` with `existing_batch_id` if the digest already exists for the org.

### RawRecord

Verbatim parsed row, preserved for forensics.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `batch` | FK → IngestionBatch | CASCADE |
| `organization` | FK | Denormalized for direct queryset filtering |
| `row_number` | IntegerField | 1-based, matches source file |
| `raw_data` | JSONField | Verbatim column-name → value dict |
| `parse_status` | CharField | `ok` / `warning` / `error` / `skipped` |
| `parse_errors` | JSONField | List of `{field, message}` dicts |
| `created_at` | DateTimeField | |

### EmissionRecord

Central accounting record. One-to-one with `RawRecord`.

**Provenance group**

| Field | Type | Notes |
|---|---|---|
| `batch` | FK → IngestionBatch | For list-level batch filtering |
| `raw_record` | OneToOneField → RawRecord | OneToOne enforces one emission per row |
| `source_type` | CharField | Denormalized from batch for fast filtering |

**Classification group**

| Field | Type | Notes |
|---|---|---|
| `scope` | IntegerField | 1, 2, or 3 |
| `activity_category` | CharField | e.g. `diesel_combustion`, `grid_electricity`, `flight_economy` |

**Activity data group**

| Field | Type | Notes |
|---|---|---|
| `activity_date` | DateField | Parsed from source |
| `vendor` | CharField | Supplier name |
| `location` | CharField | Plant / site code |
| `department` | CharField | Cost center |
| `description` | CharField | Free-text from source |

**Raw values group** — preserved verbatim from source

| Field | Type | Notes |
|---|---|---|
| `raw_quantity` | DecimalField | Source value |
| `raw_unit` | CharField | Source unit string (may be non-SI) |
| `raw_currency` | CharField | 3-letter ISO code if monetary |

**Normalized values group** — output of normalizer

| Field | Type | Notes |
|---|---|---|
| `normalized_quantity` | DecimalField | Converted to SI unit |
| `normalized_unit` | CharField | SI unit label |
| `quantity_kg_co2e` | DecimalField | Final emission quantity |
| `emission_factor_used` | FK → EmissionFactor | null if no factor matched |

**Suspicion group**

| Field | Type | Notes |
|---|---|---|
| `is_suspicious` | BooleanField | Set by normalizer; never cleared automatically |
| `suspicion_reasons` | JSONField | List of reason codes (see below) |

Suspicion reason codes:
- `zero_quantity` — activity quantity is zero
- `stale_date` — activity date >18 months before upload
- `future_date` — activity date is in the future
- `unknown_unit` — unit string not in normalization table
- `outlier_3sigma` — quantity >3σ from batch mean for this activity category

**Review workflow group**

| Field | Type | Notes |
|---|---|---|
| `review_status` | CharField | `pending` → `flagged` / `approved` / `rejected` |
| `reviewed_by` | FK → UserProfile | null=True |
| `reviewed_at` | DateTimeField | null=True |
| `review_notes` | TextField | |

**Audit lock group**

| Field | Type | Notes |
|---|---|---|
| `is_locked` | BooleanField | Admin-only. Blocks all PATCH and status changes. |
| `locked_by` | FK → UserProfile | null=True |
| `locked_at` | DateTimeField | null=True |

### EmissionFactor

Reference table for GHG conversion coefficients.

| Field | Type | Notes |
|---|---|---|
| `organization` | FK | null=True → global factor |
| `activity_category` | CharField | Matches `EmissionRecord.activity_category` |
| `scope` | IntegerField | 1, 2, or 3 |
| `kg_co2e_per_unit` | DecimalField | Conversion coefficient |
| `unit` | CharField | Denominator unit |
| `factor_source` | CharField | `epa_egrid` / `defra` / `icao` / `iea` / `custom` |
| `valid_from` | DateField | |
| `valid_to` | DateField | null=True → currently valid |

Lookup priority: org-specific factors are preferred over global factors. The normalizer calls `_get_factor(category, scope, org)` which checks org-scoped factors first.

### AuditLog

Immutable event log.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `organization` | FK | |
| `emission_record` | FK → EmissionRecord | null=True for batch-level events |
| `action` | CharField | See action codes below |
| `performed_by` | FK → UserProfile | null=True (system actions) |
| `before_state` | JSONField | Snapshot of changed fields before action |
| `after_state` | JSONField | Snapshot after action |
| `notes` | TextField | Analyst-provided note |
| `ip_address` | GenericIPAddressField | From request |
| `timestamp` | DateTimeField | auto_now_add |

Action codes: `created`, `edited`, `approved`, `rejected`, `flagged`, `unflagged`, `locked`, `unlocked`, `batch_approved`, `batch_rejected`

Immutability enforcement:
```python
def save(self, *args, **kwargs):
    if self.pk:
        raise ValueError("AuditLog entries are immutable")
    super().save(*args, **kwargs)

def delete(self, *args, **kwargs):
    raise ValueError("AuditLog entries cannot be deleted")
```

---

## Multi-Tenancy Boundary

`OrganizationScopedMixin` is applied to all DRF viewsets. It overrides `get_queryset()` to filter by `request.user.organization`. UUID primary keys mean that even without this filter, IDs from other tenants are not guessable — but the filter provides defense in depth.

---

## Scope Assignment Rules

| Source | Rule |
|---|---|
| SAP (MATKL = `FUEL`, `ENER`, `GAS`) | Scope 1 — direct combustion |
| SAP (MATKL = `ELEC`, `UTIL`) | Scope 2 — purchased electricity |
| SAP (all other MATKL) | Scope 3 — upstream supply chain |
| Utility CSV | Always Scope 2 |
| Travel CSV — flights, hotels, rail | Always Scope 3 (Category 6: Business Travel) |
