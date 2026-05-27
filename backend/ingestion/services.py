"""
Ingestion pipeline: file → RawRecords → EmissionRecords.

Runs synchronously (no Celery). Handles up to ~50k rows well within Gunicorn timeout.
For larger files, a 20MB upload cap is enforced in the API view.
"""
import hashlib
from datetime import datetime

from django.db import transaction

from ingestion.models import IngestionBatch, RawRecord
from emissions.models import AuditLog, EmissionRecord
from emissions.normalizer import normalize_row, compute_batch_stats
from parsers.sap_csv import SAPCsvParser
from parsers.utility_csv import UtilityCsvParser
from parsers.travel_csv import TravelCsvParser


PARSERS = {
    IngestionBatch.SourceType.SAP: SAPCsvParser,
    IngestionBatch.SourceType.UTILITY: UtilityCsvParser,
    IngestionBatch.SourceType.TRAVEL: TravelCsvParser,
}


def compute_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


@transaction.atomic
def process_batch(batch: IngestionBatch, file_bytes: bytes) -> IngestionBatch:
    """
    Full ingestion pipeline for one uploaded file.
    Creates RawRecord + EmissionRecord for each parseable row.
    Updates batch status and counts on completion.
    """
    batch.status = IngestionBatch.Status.PROCESSING
    batch.save(update_fields=["status"])

    parser_class = PARSERS.get(batch.source_type)
    if not parser_class:
        batch.status = IngestionBatch.Status.FAILED
        batch.parse_errors_summary = f"No parser for source type: {batch.source_type}"
        batch.save(update_fields=["status", "parse_errors_summary"])
        return batch

    try:
        parser = parser_class()
        parsed_rows = parser.parse(file_bytes)
    except Exception as exc:
        batch.status = IngestionBatch.Status.FAILED
        batch.parse_errors_summary = f"Parser crashed: {exc}"
        batch.save(update_fields=["status", "parse_errors_summary"])
        return batch

    # Compute stats for outlier detection before persisting
    valid_data = [r.data for r in parsed_rows if r.status not in ("error", "skipped")]
    batch_stats = compute_batch_stats(valid_data)

    batch.row_count_total = len([r for r in parsed_rows if r.status != "skipped"])
    raw_records_to_create = []
    raw_rows_map = []  # (parsed_row, raw_record_instance)

    # Bulk-create RawRecords first
    for parsed in parsed_rows:
        if parsed.status == "skipped":
            continue
        rr = RawRecord(
            batch=batch,
            organization=batch.organization,
            row_number=parsed.row_number,
            raw_data=parsed.data.get("_raw", parsed.data),
            parse_status=parsed.status,
            parse_errors=parsed.errors,
        )
        raw_records_to_create.append(rr)
        raw_rows_map.append((parsed, rr))

    RawRecord.objects.bulk_create(raw_records_to_create, batch_size=500)

    # Now normalize valid rows into EmissionRecords
    emission_records_to_create = []
    audit_logs_to_create = []
    failed = 0
    suspicious = 0

    for parsed, raw_record in raw_rows_map:
        if parsed.status == "error":
            failed += 1
            continue

        emission = normalize_row(
            parsed_data=parsed.data,
            batch=batch,
            raw_record=raw_record,
            organization=batch.organization,
            batch_stats=batch_stats,
        )

        if emission is None:
            failed += 1
            continue

        if emission.is_suspicious:
            suspicious += 1

        emission_records_to_create.append(emission)

    # Bulk create emission records
    created = EmissionRecord.objects.bulk_create(emission_records_to_create, batch_size=500)

    # Bulk create audit log CREATED entries
    for emission in created:
        audit_logs_to_create.append(
            AuditLog(
                organization=batch.organization,
                emission_record=emission,
                action=AuditLog.Action.CREATED,
                performed_by=batch.uploaded_by,
                after_state={
                    "scope": emission.scope,
                    "activity_category": emission.activity_category,
                    "quantity_kg_co2e": str(emission.quantity_kg_co2e),
                    "review_status": emission.review_status,
                },
            )
        )
    AuditLog.objects.bulk_create(audit_logs_to_create, batch_size=500)

    # Collect top parse errors for summary
    all_errors = []
    for parsed, _ in raw_rows_map:
        for err in parsed.errors[:2]:
            all_errors.append(f"Row {parsed.row_number}: {err.get('field')} — {err.get('message')}")
    top_errors = "\n".join(all_errors[:20])
    if len(all_errors) > 20:
        top_errors += f"\n... and {len(all_errors) - 20} more"

    batch.row_count_parsed = len(emission_records_to_create)
    batch.row_count_failed = failed
    batch.row_count_suspicious = suspicious
    batch.parse_errors_summary = top_errors
    batch.status = IngestionBatch.Status.COMPLETE
    batch.completed_at = datetime.utcnow()
    batch.save(update_fields=[
        "status", "row_count_total", "row_count_parsed",
        "row_count_failed", "row_count_suspicious",
        "parse_errors_summary", "completed_at",
    ])

    return batch
