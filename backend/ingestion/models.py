import uuid
from django.db import models
from django.conf import settings
from core.models import Organization


def batch_upload_path(instance, filename):
    return f"uploads/{instance.organization.slug}/{instance.id}/{filename}"


class IngestionBatch(models.Model):
    class SourceType(models.TextChoices):
        SAP = "sap", "SAP Procurement CSV"
        UTILITY = "utility", "Utility Portal CSV"
        TRAVEL = "travel", "Concur Travel CSV"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="batches"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_batches",
    )
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    original_filename = models.CharField(max_length=500)
    file = models.FileField(upload_to=batch_upload_path, null=True, blank=True)
    file_sha256 = models.CharField(
        max_length=64,
        help_text="SHA-256 of raw file bytes for dedup and integrity",
    )
    file_size_bytes = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    row_count_total = models.PositiveIntegerField(default=0)
    row_count_parsed = models.PositiveIntegerField(default=0)
    row_count_failed = models.PositiveIntegerField(default=0)
    row_count_suspicious = models.PositiveIntegerField(default=0)
    parse_errors_summary = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["organization", "source_type"]),
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self):
        return f"{self.source_type} | {self.original_filename} | {self.uploaded_at:%Y-%m-%d}"


class RawRecord(models.Model):
    class ParseStatus(models.TextChoices):
        OK = "ok", "Parsed OK"
        WARNING = "warning", "Parsed with warnings"
        ERROR = "error", "Parse error — not normalized"
        SKIPPED = "skipped", "Skipped (header/empty row)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        IngestionBatch, on_delete=models.CASCADE, related_name="raw_records"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="raw_records"
    )
    row_number = models.PositiveIntegerField(
        help_text="1-based row number in the source file"
    )
    raw_data = models.JSONField(help_text="Verbatim parsed row as key-value dict")
    parse_status = models.CharField(
        max_length=20, choices=ParseStatus.choices, default=ParseStatus.OK
    )
    parse_errors = models.JSONField(
        default=list,
        help_text="List of {field, message} dicts describing parse issues",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["batch", "row_number"]
        indexes = [
            models.Index(fields=["organization", "batch"]),
            models.Index(fields=["parse_status"]),
        ]
        unique_together = [("batch", "row_number")]

    def __str__(self):
        return f"Row {self.row_number} / {self.batch}"
