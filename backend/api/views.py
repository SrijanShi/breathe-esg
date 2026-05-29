import hashlib
from datetime import datetime, timedelta

from django.conf import settings
from django.db import models as dj_models
from django.db.models import Count, Sum, Q
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import UserProfile
from emissions.models import AuditLog, EmissionFactor, EmissionRecord
from ingestion.models import IngestionBatch, RawRecord
from ingestion.services import compute_sha256, process_batch

from .authentication import CookieJWTAuthentication
from .pagination import AuditLogCursorPagination, EmissionCursorPagination, SmallPagePagination, StandardCursorPagination
from .permissions import IsAdminOnly, IsAnalystOrAdmin, IsAnyOrgMember
from .serializers import (
    AuditLogSerializer,
    EmissionFactorSerializer,
    EmissionRecordDetailSerializer,
    EmissionRecordListSerializer,
    IngestionBatchSerializer,
    RawRecordSerializer,
    UserSerializer,
)


def _set_jwt_cookies(response, refresh_token):
    jwt_settings = settings.SIMPLE_JWT
    secure = jwt_settings.get("AUTH_COOKIE_SECURE", False)
    samesite = jwt_settings.get("AUTH_COOKIE_SAMESITE", "Lax")
    http_only = jwt_settings.get("AUTH_COOKIE_HTTP_ONLY", True)

    response.set_cookie(
        jwt_settings.get("AUTH_COOKIE", "access_token"),
        str(refresh_token.access_token),
        max_age=int(jwt_settings["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        httponly=http_only,
        secure=secure,
        samesite=samesite,
        path="/",
    )
    response.set_cookie(
        jwt_settings.get("AUTH_COOKIE_REFRESH", "refresh_token"),
        str(refresh_token),
        max_age=int(jwt_settings["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=http_only,
        secure=secure,
        samesite=samesite,
        path="/",
    )


def _clear_jwt_cookies(response):
    jwt_settings = settings.SIMPLE_JWT
    response.delete_cookie(jwt_settings.get("AUTH_COOKIE", "access_token"))
    response.delete_cookie(jwt_settings.get("AUTH_COOKIE_REFRESH", "refresh_token"))


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username") or request.data.get("email")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"detail": "Username/email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.contrib.auth import authenticate
        user = authenticate(request, username=username, password=password)

        if user is None:
            # Try email lookup
            try:
                user_obj = UserProfile.objects.get(email=username)
                user = authenticate(request, username=user_obj.username, password=password)
            except UserProfile.DoesNotExist:
                user = None

        if user is None or not user.is_active:
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        response = Response({"detail": "Login successful.", "user": UserSerializer(user).data})
        _set_jwt_cookies(response, refresh)
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get(
            settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "refresh_token")
        )
        if not refresh_token:
            refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"detail": "No refresh token provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refresh = RefreshToken(refresh_token)
            response = Response({"detail": "Token refreshed."})
            _set_jwt_cookies(response, refresh)
            return response
        except TokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    def post(self, request):
        refresh_token = request.COOKIES.get(
            settings.SIMPLE_JWT.get("AUTH_COOKIE_REFRESH", "refresh_token")
        )
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except (TokenError, Exception):
                pass

        response = Response({"detail": "Logged out."})
        _clear_jwt_cookies(response)
        return response


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class DashboardKPIsView(APIView):
    permission_classes = [IsAnyOrgMember]

    def get(self, request):
        org = request.user.organization
        qs = EmissionRecord.objects.filter(organization=org)

        total = qs.count()
        pending = qs.filter(review_status=EmissionRecord.ReviewStatus.PENDING).count()
        flagged = qs.filter(review_status=EmissionRecord.ReviewStatus.FLAGGED).count()
        approved = qs.filter(review_status=EmissionRecord.ReviewStatus.APPROVED).count()
        rejected = qs.filter(review_status=EmissionRecord.ReviewStatus.REJECTED).count()
        locked = qs.filter(is_locked=True).count()

        scope_totals = (
            qs.values("scope")
            .annotate(
                count=Count("id"),
                total_kg_co2e=Sum("quantity_kg_co2e"),
            )
            .order_by("scope")
        )

        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_batches = IngestionBatch.objects.filter(
            organization=org,
            uploaded_at__gte=thirty_days_ago,
        )
        ingestion_health = {
            "total": recent_batches.count(),
            "complete": recent_batches.filter(status=IngestionBatch.Status.COMPLETE).count(),
            "failed": recent_batches.filter(status=IngestionBatch.Status.FAILED).count(),
            "processing": recent_batches.filter(status=IngestionBatch.Status.PROCESSING).count(),
        }

        return Response({
            "total_records": total,
            "pending": pending,
            "flagged": flagged,
            "approved": approved,
            "rejected": rejected,
            "locked": locked,
            "needs_attention": pending + flagged,
            "scope_totals": list(scope_totals),
            "ingestion_health_30d": ingestion_health,
        })


class ScopeBreakdownView(APIView):
    permission_classes = [IsAnyOrgMember]

    def get(self, request):
        org = request.user.organization
        months_back = int(request.query_params.get("months", 36))

        from django.db.models.functions import TruncMonth
        cutoff = timezone.now() - timedelta(days=months_back * 30)

        data = (
            EmissionRecord.objects.filter(organization=org, activity_date__gte=cutoff.date())
            .annotate(month=TruncMonth("activity_date"))
            .values("month", "scope")
            .annotate(total_kg_co2e=Sum("quantity_kg_co2e"))
            .order_by("month", "scope")
        )

        return Response([
            {
                "month": d["month"].strftime("%Y-%m"),
                "scope": d["scope"],
                "total_kg_co2e": float(d["total_kg_co2e"] or 0),
                "total_t_co2e": float(d["total_kg_co2e"] or 0) / 1000,
            }
            for d in data
        ])


class OrganizationScopedMixin:
    """Ensures all queryset operations are scoped to the requesting user's organization."""

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(self.request.user, "organization") and self.request.user.organization:
            return qs.filter(organization=self.request.user.organization)
        return qs.none()


class IngestionBatchViewSet(OrganizationScopedMixin, ModelViewSet):
    serializer_class = IngestionBatchSerializer
    permission_classes = [IsAnalystOrAdmin]
    pagination_class = SmallPagePagination
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        org = self.request.user.organization
        qs = IngestionBatch.objects.filter(organization=org)

        source = self.request.query_params.get("source_type")
        if source:
            qs = qs.filter(source_type=source)

        batch_status = self.request.query_params.get("status")
        if batch_status:
            qs = qs.filter(status=batch_status)

        return qs.order_by("-uploaded_at")

    def create(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        source_type = request.data.get("source_type")

        if not file:
            return Response({"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        if source_type not in IngestionBatch.SourceType.values:
            return Response(
                {"detail": f"Invalid source_type. Choose from: {IngestionBatch.SourceType.values}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_bytes = getattr(settings, "MAX_UPLOAD_SIZE_MB", 20) * 1024 * 1024
        if file.size > max_bytes:
            return Response(
                {"detail": f"File too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_bytes = file.read()
        sha256 = compute_sha256(file_bytes)

        # SHA-256 dedup check
        existing = IngestionBatch.objects.filter(
            organization=request.user.organization,
            file_sha256=sha256,
        ).first()
        if existing:
            return Response(
                {
                    "detail": "This file has already been uploaded.",
                    "existing_batch_id": str(existing.id),
                    "uploaded_at": existing.uploaded_at,
                },
                status=status.HTTP_409_CONFLICT,
            )

        batch = IngestionBatch.objects.create(
            organization=request.user.organization,
            uploaded_by=request.user,
            source_type=source_type,
            original_filename=file.name,
            file_sha256=sha256,
            file_size_bytes=file.size,
            status=IngestionBatch.Status.PENDING,
        )

        # Synchronous processing
        process_batch(batch, file_bytes)
        batch.refresh_from_db()

        return Response(
            IngestionBatchSerializer(batch).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="raw-records")
    def raw_records(self, request, pk=None):
        batch = self.get_object()
        qs = RawRecord.objects.filter(batch=batch).order_by("row_number")
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(RawRecordSerializer(page, many=True).data)
        return Response(RawRecordSerializer(qs, many=True).data)

    def destroy(self, request, *args, **kwargs):
        batch = self.get_object()
        if batch.emission_records.filter(is_locked=True).exists():
            return Response(
                {"detail": "Cannot delete a batch with locked records."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class RawRecordViewSet(OrganizationScopedMixin, ReadOnlyModelViewSet):
    serializer_class = RawRecordSerializer
    permission_classes = [IsAnyOrgMember]
    pagination_class = StandardCursorPagination

    def get_queryset(self):
        return RawRecord.objects.filter(organization=self.request.user.organization)


def _write_audit_log(record, action, user, request, notes="", before=None, after=None):
    ip = request.META.get("REMOTE_ADDR") or request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
    AuditLog.objects.create(
        organization=record.organization,
        emission_record=record,
        action=action,
        performed_by=user,
        before_state=before,
        after_state=after,
        notes=notes,
        ip_address=ip or None,
    )


class EmissionRecordViewSet(OrganizationScopedMixin, ModelViewSet):
    permission_classes = [IsAnyOrgMember]
    pagination_class = EmissionCursorPagination
    http_method_names = ["get", "patch", "head", "options", "post"]

    def get_serializer_class(self):
        if self.action in ("retrieve", "partial_update"):
            return EmissionRecordDetailSerializer
        return EmissionRecordListSerializer

    def get_queryset(self):
        org = self.request.user.organization
        qs = EmissionRecord.objects.filter(organization=org).select_related(
            "batch", "reviewed_by", "locked_by"
        )

        # Filters
        params = self.request.query_params
        scope = params.get("scope")
        if scope:
            qs = qs.filter(scope=scope)

        source = params.get("source_type")
        if source:
            qs = qs.filter(source_type=source)

        review_status = params.get("review_status")
        if review_status:
            qs = qs.filter(review_status=review_status)

        suspicious = params.get("is_suspicious")
        if suspicious in ("true", "1"):
            qs = qs.filter(is_suspicious=True)
        elif suspicious in ("false", "0"):
            qs = qs.filter(is_suspicious=False)

        locked = params.get("is_locked")
        if locked in ("true", "1"):
            qs = qs.filter(is_locked=True)
        elif locked in ("false", "0"):
            qs = qs.filter(is_locked=False)

        date_from = params.get("date_from")
        if date_from:
            qs = qs.filter(activity_date__gte=date_from)

        date_to = params.get("date_to")
        if date_to:
            qs = qs.filter(activity_date__lte=date_to)

        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(vendor__icontains=search)
                | Q(location__icontains=search)
                | Q(activity_category__icontains=search)
                | Q(description__icontains=search)
            )

        batch_id = params.get("batch")
        if batch_id:
            qs = qs.filter(batch_id=batch_id)

        return qs.order_by("-activity_date")

    def partial_update(self, request, *args, **kwargs):
        record = self.get_object()
        if record.is_locked:
            return Response(
                {"detail": "This record is locked for audit. Contact an admin to unlock."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if request.user.role == UserProfile.Role.AUDITOR:
            return Response({"detail": "Auditors cannot edit records."}, status=status.HTTP_403_FORBIDDEN)

        before = {
            "review_status": record.review_status,
            "normalized_quantity": str(record.normalized_quantity),
            "quantity_kg_co2e": str(record.quantity_kg_co2e),
        }
        response = super().partial_update(request, *args, **kwargs)
        record.refresh_from_db()
        after = {
            "review_status": record.review_status,
            "normalized_quantity": str(record.normalized_quantity),
            "quantity_kg_co2e": str(record.quantity_kg_co2e),
        }
        _write_audit_log(record, AuditLog.Action.EDITED, request.user, request, before=before, after=after)
        return response

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        record = self.get_object()
        if record.is_locked:
            return Response({"detail": "Record is locked."}, status=status.HTTP_400_BAD_REQUEST)
        if request.user.role == UserProfile.Role.AUDITOR:
            return Response({"detail": "Auditors cannot approve records."}, status=status.HTTP_403_FORBIDDEN)

        before = {"review_status": record.review_status}
        record.review_status = EmissionRecord.ReviewStatus.APPROVED
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.review_notes = request.data.get("notes", "")
        record.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "review_notes"])
        _write_audit_log(
            record, AuditLog.Action.APPROVED, request.user, request,
            notes=record.review_notes,
            before=before,
            after={"review_status": record.review_status},
        )
        return Response(EmissionRecordListSerializer(record).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        record = self.get_object()
        if record.is_locked:
            return Response({"detail": "Record is locked."}, status=status.HTTP_400_BAD_REQUEST)
        if request.user.role == UserProfile.Role.AUDITOR:
            return Response({"detail": "Auditors cannot reject records."}, status=status.HTTP_403_FORBIDDEN)

        notes = request.data.get("notes", "").strip()
        if not notes:
            return Response({"detail": "Rejection requires a note explaining the reason."}, status=status.HTTP_400_BAD_REQUEST)

        before = {"review_status": record.review_status}
        record.review_status = EmissionRecord.ReviewStatus.REJECTED
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.review_notes = notes
        record.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "review_notes"])
        _write_audit_log(
            record, AuditLog.Action.REJECTED, request.user, request,
            notes=notes,
            before=before,
            after={"review_status": record.review_status},
        )
        return Response(EmissionRecordListSerializer(record).data)

    @action(detail=True, methods=["post"])
    def flag(self, request, pk=None):
        record = self.get_object()
        if record.is_locked:
            return Response({"detail": "Record is locked."}, status=status.HTTP_400_BAD_REQUEST)

        before = {"is_suspicious": record.is_suspicious, "review_status": record.review_status}
        if record.is_suspicious:
            record.is_suspicious = False
            record.suspicion_reasons = []
            record.review_status = EmissionRecord.ReviewStatus.PENDING
            action_label = AuditLog.Action.UNFLAGGED
        else:
            record.is_suspicious = True
            reason = request.data.get("reason", "manual_flag")
            record.suspicion_reasons = [reason]
            record.review_status = EmissionRecord.ReviewStatus.FLAGGED
            action_label = AuditLog.Action.FLAGGED

        record.save(update_fields=["is_suspicious", "suspicion_reasons", "review_status"])
        _write_audit_log(
            record, action_label, request.user, request,
            before=before,
            after={"is_suspicious": record.is_suspicious, "review_status": record.review_status},
        )
        return Response(EmissionRecordListSerializer(record).data)

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        if request.user.role != UserProfile.Role.ADMIN:
            return Response({"detail": "Only admins can lock records."}, status=status.HTTP_403_FORBIDDEN)
        record = self.get_object()
        if record.review_status != EmissionRecord.ReviewStatus.APPROVED:
            return Response(
                {"detail": "Only approved records can be locked for audit."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if record.is_locked:
            return Response({"detail": "Record is already locked."}, status=status.HTTP_400_BAD_REQUEST)

        before = {"is_locked": False}
        record.is_locked = True
        record.locked_by = request.user
        record.locked_at = timezone.now()
        record.save(update_fields=["is_locked", "locked_by", "locked_at"])
        _write_audit_log(record, AuditLog.Action.LOCKED, request.user, request, before=before, after={"is_locked": True})
        return Response(EmissionRecordListSerializer(record).data)

    @action(detail=False, methods=["post"], url_path="bulk-approve")
    def bulk_approve(self, request):
        if request.user.role == UserProfile.Role.AUDITOR:
            return Response({"detail": "Auditors cannot approve records."}, status=status.HTTP_403_FORBIDDEN)

        ids = request.data.get("ids", [])
        if not ids:
            return Response({"detail": "No IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

        org = request.user.organization
        records = EmissionRecord.objects.filter(
            id__in=ids, organization=org, is_locked=False
        ).exclude(review_status=EmissionRecord.ReviewStatus.APPROVED)

        now = timezone.now()
        notes = request.data.get("notes", "")
        updated_ids = []
        audit_logs = []

        for record in records:
            before = {"review_status": record.review_status}
            record.review_status = EmissionRecord.ReviewStatus.APPROVED
            record.reviewed_by = request.user
            record.reviewed_at = now
            record.review_notes = notes
            updated_ids.append(record.id)
            audit_logs.append(AuditLog(
                organization=org,
                emission_record=record,
                action=AuditLog.Action.BATCH_APPROVED,
                performed_by=request.user,
                before_state=before,
                after_state={"review_status": EmissionRecord.ReviewStatus.APPROVED},
                notes=notes,
            ))

        EmissionRecord.objects.bulk_update(
            records, ["review_status", "reviewed_by", "reviewed_at", "review_notes"]
        )
        AuditLog.objects.bulk_create(audit_logs, batch_size=500)

        return Response({"approved": len(updated_ids), "ids": [str(i) for i in updated_ids]})

    @action(detail=False, methods=["post"], url_path="bulk-reject")
    def bulk_reject(self, request):
        if request.user.role == UserProfile.Role.AUDITOR:
            return Response({"detail": "Auditors cannot reject records."}, status=status.HTTP_403_FORBIDDEN)

        ids = request.data.get("ids", [])
        notes = request.data.get("notes", "").strip()
        if not ids:
            return Response({"detail": "No IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
        if not notes:
            return Response({"detail": "Bulk rejection requires a note."}, status=status.HTTP_400_BAD_REQUEST)

        org = request.user.organization
        records = EmissionRecord.objects.filter(
            id__in=ids, organization=org, is_locked=False
        ).exclude(review_status=EmissionRecord.ReviewStatus.REJECTED)

        now = timezone.now()
        updated_ids = []
        audit_logs = []

        for record in records:
            before = {"review_status": record.review_status}
            record.review_status = EmissionRecord.ReviewStatus.REJECTED
            record.reviewed_by = request.user
            record.reviewed_at = now
            record.review_notes = notes
            updated_ids.append(record.id)
            audit_logs.append(AuditLog(
                organization=org,
                emission_record=record,
                action=AuditLog.Action.BATCH_REJECTED,
                performed_by=request.user,
                before_state=before,
                after_state={"review_status": EmissionRecord.ReviewStatus.REJECTED},
                notes=notes,
            ))

        EmissionRecord.objects.bulk_update(
            records, ["review_status", "reviewed_by", "reviewed_at", "review_notes"]
        )
        AuditLog.objects.bulk_create(audit_logs, batch_size=500)

        return Response({"rejected": len(updated_ids), "ids": [str(i) for i in updated_ids]})

    @action(detail=True, methods=["get"])
    def audit(self, request, pk=None):
        record = self.get_object()
        logs = AuditLog.objects.filter(emission_record=record).order_by("timestamp")
        return Response(AuditLogSerializer(logs, many=True).data)

    @action(detail=False, methods=["get"])
    def export(self, request):
        import csv as csv_module
        from django.http import StreamingHttpResponse

        org = request.user.organization
        qs = self.get_queryset()

        def stream_csv():
            yield "scope,source_type,activity_category,activity_date,vendor,location,raw_quantity,raw_unit,normalized_quantity,normalized_unit,quantity_kg_co2e,tonnes_co2e,review_status,is_locked\n"
            for r in qs.iterator(chunk_size=500):
                yield (
                    f"{r.scope},{r.source_type},{r.activity_category},{r.activity_date},"
                    f'"{r.vendor}","{r.location}",'
                    f"{r.raw_quantity},{r.raw_unit},"
                    f"{r.normalized_quantity},{r.normalized_unit},"
                    f"{r.quantity_kg_co2e},{float(r.quantity_kg_co2e)/1000},"
                    f"{r.review_status},{r.is_locked}\n"
                )

        response = StreamingHttpResponse(stream_csv(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="emissions_export.csv"'
        return response


class AuditLogViewSet(OrganizationScopedMixin, ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAnyOrgMember]
    pagination_class = AuditLogCursorPagination

    def get_queryset(self):
        org = self.request.user.organization
        qs = AuditLog.objects.filter(organization=org).select_related("performed_by")

        params = self.request.query_params
        action_filter = params.get("action")
        if action_filter:
            qs = qs.filter(action=action_filter)
        elif params.get("include_created") != "1":
            qs = qs.exclude(action=AuditLog.Action.CREATED)

        user_filter = params.get("user")
        if user_filter:
            qs = qs.filter(performed_by__username=user_filter)

        record_filter = params.get("record")
        if record_filter:
            qs = qs.filter(emission_record_id=record_filter)

        return qs.order_by("-timestamp")


class EmissionFactorViewSet(ReadOnlyModelViewSet):
    serializer_class = EmissionFactorSerializer
    permission_classes = [IsAnyOrgMember]
    pagination_class = None

    def get_queryset(self):
        org = self.request.user.organization
        return EmissionFactor.objects.filter(
            dj_models.Q(organization=org) | dj_models.Q(organization__isnull=True),
            valid_to__isnull=True,
        ).order_by("scope", "activity_category")
