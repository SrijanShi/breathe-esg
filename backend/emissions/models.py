import uuid
from django.db import models
from django.conf import settings
from core.models import Organization
from ingestion.models import IngestionBatch, RawRecord


class EmissionFactor(models.Model):
    class FactorSource(models.TextChoices):
        EPA_EGRID = "epa_egrid", "EPA eGRID"
        DEFRA = "defra", "UK DEFRA"
        ICAO = "icao", "ICAO Aviation"
        IEA = "iea", "IEA"
        EPA_USEEIO = "epa_useeio", "EPA USEEIO"
        CUSTOM = "custom", "Organization Custom"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Null = global factor; non-null = org-specific override",
    )
    activity_category = models.CharField(
        max_length=100,
        help_text="e.g. 'electricity_kwh_us_average', 'diesel_litre', 'flight_km_economy'",
    )
    scope = models.PositiveSmallIntegerField(
        choices=[(1, "Scope 1"), (2, "Scope 2"), (3, "Scope 3")]
    )
    kg_co2e_per_unit = models.DecimalField(max_digits=14, decimal_places=8)
    unit = models.CharField(max_length=32, help_text="Denominator unit, e.g. 'kWh', 'litre', 'km'")
    factor_source = models.CharField(max_length=20, choices=FactorSource.choices)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["activity_category", "scope"]),
        ]

    def __str__(self):
        return f"{self.activity_category} @ {self.kg_co2e_per_unit} kgCO2e/{self.unit}"


class EmissionRecord(models.Model):
    class Scope(models.IntegerChoices):
        SCOPE_1 = 1, "Scope 1 — Direct"
        SCOPE_2 = 2, "Scope 2 — Purchased Energy"
        SCOPE_3 = 3, "Scope 3 — Value Chain"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending Review"
        FLAGGED = "flagged", "Flagged / Suspicious"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="emission_records"
    )

    # Provenance — which file/row produced this record
    batch = models.ForeignKey(
        IngestionBatch,
        on_delete=models.PROTECT,
        related_name="emission_records",
    )
    raw_record = models.OneToOneField(
        RawRecord,
        on_delete=models.PROTECT,
        related_name="emission_record",
        null=True,
        blank=True,
    )
    source_type = models.CharField(
        max_length=20,
        choices=IngestionBatch.SourceType.choices,
        help_text="Denormalized from batch for fast filtering",
    )

    # Classification
    scope = models.PositiveSmallIntegerField(choices=Scope.choices)
    activity_category = models.CharField(
        max_length=100,
        help_text="e.g. 'diesel', 'electricity', 'flight_economy', 'hotel_night'",
    )

    # Activity data
    activity_date = models.DateField(
        help_text="Date the activity occurred (not the ingestion date)"
    )
    vendor = models.CharField(max_length=255, blank=True)
    location = models.CharField(
        max_length=255,
        blank=True,
        help_text="Plant code, service address, city-pair, etc.",
    )
    department = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    # Raw values — preserved verbatim for traceability
    raw_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    raw_unit = models.CharField(max_length=32, help_text="Unit as it appeared in source")
    raw_currency = models.CharField(max_length=3, blank=True, help_text="ISO 4217")

    # Normalized values
    normalized_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        help_text="Quantity in emission factor's denominator unit",
    )
    normalized_unit = models.CharField(max_length=32)
    quantity_kg_co2e = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        help_text="Calculated emission in kg CO2-equivalent",
    )
    emission_factor_used = models.ForeignKey(
        EmissionFactor,
        on_delete=models.PROTECT,
        null=True,
        related_name="applied_records",
    )

    # Suspicion flags — set by rules engine post-normalization
    is_suspicious = models.BooleanField(default=False)
    suspicion_reasons = models.JSONField(
        default=list,
        help_text="List of reason codes, e.g. ['outlier_3sigma', 'stale_date']",
    )

    # Review workflow
    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_records",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # Audit lock — once locked no further edits permitted
    is_locked = models.BooleanField(default=False)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="locked_records",
    )
    locked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-activity_date", "scope"]
        indexes = [
            models.Index(fields=["organization", "scope", "review_status"]),
            models.Index(fields=["organization", "activity_date"]),
            models.Index(fields=["organization", "source_type"]),
            models.Index(fields=["organization", "is_locked"]),
            models.Index(fields=["is_suspicious", "review_status"]),
        ]

    def __str__(self):
        return (
            f"Scope {self.scope} | {self.activity_category} | "
            f"{self.activity_date} | {self.quantity_kg_co2e} kgCO2e"
        )

    @property
    def tonnes_co2e(self):
        return float(self.quantity_kg_co2e) / 1000


class AuditLog(models.Model):
    """Immutable append-only record of every state change on EmissionRecord."""

    class Action(models.TextChoices):
        CREATED = "created", "Record Created"
        EDITED = "edited", "Field Edited"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        FLAGGED = "flagged", "Flagged as Suspicious"
        UNFLAGGED = "unflagged", "Suspicion Cleared"
        LOCKED = "locked", "Locked for Audit"
        UNLOCKED = "unlocked", "Unlocked (Admin)"
        BATCH_APPROVED = "batch_approved", "Bulk Approved"
        BATCH_REJECTED = "batch_rejected", "Bulk Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="audit_logs"
    )
    emission_record = models.ForeignKey(
        EmissionRecord,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_actions",
    )
    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["emission_record", "timestamp"]),
            models.Index(fields=["organization", "timestamp"]),
            models.Index(fields=["performed_by", "timestamp"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("AuditLog entries are immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditLog entries cannot be deleted.")

    def __str__(self):
        return f"{self.action} on {self.emission_record_id} by {self.performed_by} at {self.timestamp}"
