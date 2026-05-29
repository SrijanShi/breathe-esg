# Architecture Decisions

## Source Format Selection

### Why flat-file CSV upload instead of live API integration?

All three sources (SAP, utility portals, Concur) have live API options. We chose flat-file upload for every source. The reasons are consistent across all three:

**SAP Procurement**

SAP's live integration paths are SAP IDoc (requires middleware, BASIS team access, and RFC ports open from the ESG platform to the ERP) and OData services (requires a live NetWeaver gateway, OAuth credentials scoped per org, and API-version pinning against the customer's SAP release). Neither is feasible for a prototype or for customers who have SAP in an isolated network segment.

The SAP ME2N / MIRO flat-file export is a standard scheduled report that every SAP basis team can configure. The German field names (BUKRS, BLDAT, MATNR, MENGE, MEINS, WERKS, LIFNR) are stable across SAP versions and locales. The parser handles the DD.MM.YYYY date format, MEINS unit codes (GL, MT, KG, L, M3, MWH, KWH, GJ), and the MATKL material group hierarchy for scope classification.

**Utility Data (Green Button Alliance)**

Utility APIs require per-utility OAuth registration — there are >3,000 US utilities and each has a separate API endpoint and approval process. PDF bill parsing is brittle (no standard layout). The Green Button Alliance portal CSV is a published ESPI (Energy Service Provider Interface) standard that all major US utilities support and that customers can export from their utility portal without IT involvement.

**Corporate Travel (Concur)**

Navan and TripActions both have modern APIs, but they require enterprise OAuth credentials and are not universally used. The SAP Concur standard expense report CSV is available to every Concur customer via the standard reporting portal, covers all travel modes (flights, hotels, rail), and is stable across Concur versions.

**Unified benefit:** All three sources use the same upload UX and the same pipeline. Files become evidence artifacts that are attached to the batch record. No live credential management, no per-customer API configuration, no network connectivity requirements.

---

## Authentication: JWT in httpOnly Cookies

**Alternatives considered:**
- Bearer tokens in Authorization header (localStorage)
- Session cookies (Django's built-in session framework)
- JWT in httpOnly cookies (chosen)

**Why not localStorage:** XSS can steal tokens stored in localStorage. httpOnly cookies are inaccessible to JavaScript.

**Why not Django sessions:** Sessions require sticky-session or shared-cache infrastructure for horizontal scaling. JWT is stateless. For a prototype, sessions would work, but the decision would need to be reversed for production scale.

**Why httpOnly cookies with JWT:** Tokens are invisible to JavaScript (XSS-safe). SameSite=Lax in development prevents cross-origin requests in dev. SameSite=None;Secure in production with explicit CORS allowlist prevents CSRF from non-allowlisted origins. The refresh token is also in a httpOnly cookie, so the client never stores credentials.

The `CookieJWTAuthentication` class in `api/authentication.py` reads from the configured cookie name first, then falls back to the `Authorization` header to support programmatic API clients.

---

## Synchronous Ingestion (No Celery)

The most common pattern for file ingestion in Django is Celery + Redis: upload the file, queue a task, poll for status. We chose synchronous processing instead.

**Why synchronous is acceptable here:**
- Parse time for a 20MB CSV at ~100 bytes/row is under 5 seconds in testing
- The 20MB upload cap (enforced in `IngestionBatchViewSet`) prevents runaway ingestion
- Gunicorn is configured with a 120-second timeout, well above the expected parse time
- The analyst upload flow is low-concurrency (enterprise, not consumer)

**What we lose:** A file that takes longer than the timeout causes a 502 from the reverse proxy. This is the documented failure mode in TRADEOFFS.md.

**What we gain:** No Redis dependency, no Celery worker process, no retry logic to implement, simpler Railway deployment (one dyno instead of three).

---

## UUID Primary Keys

All models use `UUIDField(default=uuid.uuid4, editable=False)` as primary key.

**Why:** Sequential integer PKs let a curious user enumerate records across organizations by incrementing the ID in the URL. UUID PKs make enumeration infeasible even without the `OrganizationScopedMixin` filter. Defense in depth.

---

## Location-based Scope 2 Only

The GHG Protocol permits two methods for Scope 2 electricity accounting:
- **Location-based:** uses the average grid emission factor for the region
- **Market-based:** uses supplier-specific factors, RECs, or GOs to reflect renewable procurement

We implement location-based only. Market-based accounting requires:
- A certificate data model (REC/REGO/GO with vintage, registry ID, and matching logic)
- Supplier disclosure data (residual mix factors per country/region)
- Certificate retirement tracking

This is documented in TRADEOFFS.md. Auditors are informed via a UI note in the Scope 2 factor display.

---

## Haversine Distance Fallback (Travel Parser)

Concur expense reports sometimes omit the `Distance` field, especially for one-way segments or after manual expense entry. The travel parser uses a static lookup table of IATA city codes with lat/lon coordinates (top-100 airports by traffic) and falls back to haversine great-circle distance when `Distance` is blank.

Haversine gives the straight-line distance between airports, not the actual route flown. For long-haul routes this is close to the actual flight path. For routes with detours or stopover legs, it underestimates. This is the industry-standard fallback used by DEFRA's travel carbon calculator.

---

## Cursor-based Pagination

All list endpoints use cursor-based pagination (`StandardCursorPagination`) rather than offset pagination.

**Why:** Offset pagination is inconsistent under concurrent writes — a record inserted between page 1 and page 2 requests causes a row to appear on both pages. Cursor pagination is stable: the cursor encodes position in the ordering, so new records inserted after the cursor position don't affect current page results. This matters for the Review Queue, where analysts are approving records while the list is open.
