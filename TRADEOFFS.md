# Deliberate Cuts

These are three capabilities that a production ESG platform would have, but that this prototype intentionally omits. Each cut was made consciously, with documented consequences.

---

## 1. No Async Task Queue (Celery / Redis)

**What was cut:** Background task processing for file ingestion. In production, large file uploads would be queued via Celery, processed by a worker, with the client polling or receiving a WebSocket/SSE notification on completion.

**What we do instead:** Synchronous parse inside the request/response cycle. The Django view calls `process_batch()` directly and returns when parsing is complete.

**Consequences:**
- Upload requests are blocked until parsing finishes. With the 20MB cap, this is under 5 seconds in testing.
- If parsing exceeds the Gunicorn 120-second timeout (e.g., a malformed file that causes quadratic backtracking in a parser), the client receives a 502 and the batch is left in `processing` status. A management command would be needed to reset it.
- Railway's free tier has a 30-second request timeout on the HTTP layer. A file approaching 20MB could hit this. The production fix is Celery + Redis (adds one Railway service), which was not added to keep the prototype deployment simple.

**Why this cut is acceptable for the prototype:** The primary workflow is analyst upload of monthly exports. These are small-to-medium CSVs (typically 500–5,000 rows). The 5-second synchronous parse is imperceptible to the analyst.

---

## 2. No Real-time Push (WebSocket / SSE)

**What was cut:** Server-sent events or WebSocket notifications for batch status updates and review queue changes.

**What we do instead:** TanStack Query polls the dashboard KPIs every 30 seconds (`refetchInterval: 30_000`). The ingestion page refetches the batch list on successful upload. The review queue refetches after every approve/reject action.

**Consequences:**
- If two analysts are reviewing the same queue simultaneously, one may approve a record and the other won't see the status change until their next action or page refresh. This creates a brief window where both analysts could attempt to approve the same record. The backend handles this gracefully (a second `approve` on an already-approved record is a no-op), but the UI may briefly show stale status.
- No live badge count on the sidebar navigation. The "Needs attention" count on the dashboard updates every 30 seconds.

**Why this cut is acceptable for the prototype:** Enterprise analyst workflows are not real-time. Analysts typically work through queue batches sequentially, not concurrently. The 30-second polling interval is sufficient for the demo workflow.

**Production path:** Django Channels + ASGI + Redis channel layer. Adds a third Railway service (Redis) and requires migrating from Gunicorn to Daphne/Uvicorn. Not complex, but not trivial either.

---

## 3. Location-based Scope 2 Only (No Market-based Accounting)

**What was cut:** GHG Protocol market-based Scope 2 accounting, which allows organizations to claim credit for renewable energy procurement via RECs (US), GOs (Europe), I-RECs (international), or supplier-specific emission rates.

**What we do instead:** Location-based Scope 2 accounting using regional average grid emission factors from EPA eGRID 2022 (US) and IEA 2023 (international). The `default_electricity_grid` field on `Organization` selects the applicable factor.

**Consequences:**
- Organizations with significant renewable energy procurement (PPAs, RECs) cannot reflect this in their Scope 2 figure. Location-based and market-based Scope 2 figures can differ by 50–90% for organizations with aggressive renewable procurement.
- The platform cannot produce a market-based Scope 2 disclosure, which is required for GHG Protocol Corporate Standard compliance when market instruments are used.
- Auditors reviewing the platform output should note: "Scope 2 figures are location-based only. Market-based figures require certificate data not captured in this system."

**Why this cut is acceptable for the prototype:** Location-based Scope 2 is the mandatory baseline method in the GHG Protocol. Market-based is optional and additive. A prototype can demonstrate the full workflow with location-based data. The `EmissionFactor` model is designed to accept `custom` source factors, so org-specific factors could be added manually for market-based calculation without model changes.

**Production path:** Add a `RenewableCertificate` model (registry ID, vintage year, MWh, certificate type, retirement date, matched_to FK → EmissionRecord). Add matching logic in the normalizer. Source certificate data from RE100, EnergyTag, or direct utility disclosure files.
