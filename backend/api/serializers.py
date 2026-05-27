from rest_framework import serializers
from core.models import Organization, UserProfile
from ingestion.models import IngestionBatch, RawRecord
from emissions.models import EmissionFactor, EmissionRecord, AuditLog


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "fiscal_year_start_month", "default_electricity_grid"]


class UserSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = ["id", "email", "username", "first_name", "last_name", "role", "organization"]
        read_only_fields = fields


class IngestionBatchSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = IngestionBatch
        fields = [
            "id", "source_type", "original_filename", "file_sha256",
            "file_size_bytes", "status",
            "row_count_total", "row_count_parsed", "row_count_failed", "row_count_suspicious",
            "parse_errors_summary", "uploaded_at", "completed_at", "uploaded_by_name",
        ]
        read_only_fields = fields

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.username
        return None


class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = ["id", "row_number", "raw_data", "parse_status", "parse_errors", "created_at"]
        read_only_fields = fields


class EmissionFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionFactor
        fields = [
            "id", "activity_category", "scope", "kg_co2e_per_unit", "unit",
            "factor_source", "valid_from", "valid_to", "notes",
        ]
        read_only_fields = fields


class EmissionRecordListSerializer(serializers.ModelSerializer):
    """Compact serializer for list view — omits heavy nested fields."""
    tonnes_co2e = serializers.FloatField(read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = EmissionRecord
        fields = [
            "id", "scope", "source_type", "activity_category", "activity_date",
            "vendor", "location", "department",
            "raw_quantity", "raw_unit", "raw_currency",
            "normalized_quantity", "normalized_unit", "quantity_kg_co2e", "tonnes_co2e",
            "is_suspicious", "suspicion_reasons",
            "review_status", "reviewed_by_name", "reviewed_at", "review_notes",
            "is_locked", "locked_at",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "scope", "source_type", "activity_category",
            "raw_quantity", "raw_unit", "quantity_kg_co2e", "tonnes_co2e",
            "is_suspicious", "suspicion_reasons",
            "review_status", "reviewed_by_name", "reviewed_at",
            "is_locked", "locked_at", "created_at", "updated_at",
        ]

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None


class EmissionRecordDetailSerializer(EmissionRecordListSerializer):
    """Full serializer for detail/edit view — includes provenance."""
    batch = IngestionBatchSerializer(read_only=True)
    raw_record = RawRecordSerializer(read_only=True)
    emission_factor_used = EmissionFactorSerializer(read_only=True)

    class Meta(EmissionRecordListSerializer.Meta):
        fields = EmissionRecordListSerializer.Meta.fields + [
            "batch", "raw_record", "emission_factor_used", "description",
        ]
        read_only_fields = [
            f for f in EmissionRecordListSerializer.Meta.read_only_fields
        ] + ["batch", "raw_record", "emission_factor_used"]


class AuditLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id", "action", "performed_by_name", "before_state", "after_state",
            "notes", "ip_address", "timestamp",
        ]
        read_only_fields = fields

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.username
        return "System"
