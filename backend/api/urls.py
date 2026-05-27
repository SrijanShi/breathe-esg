from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"ingestion/batches", views.IngestionBatchViewSet, basename="batch")
router.register(r"ingestion/raw-records", views.RawRecordViewSet, basename="rawrecord")
router.register(r"emissions", views.EmissionRecordViewSet, basename="emission")
router.register(r"audit", views.AuditLogViewSet, basename="audit")
router.register(r"emission-factors", views.EmissionFactorViewSet, basename="factor")

urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/refresh/", views.RefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("dashboard/kpis/", views.DashboardKPIsView.as_view(), name="dashboard-kpis"),
    path("dashboard/scope-breakdown/", views.ScopeBreakdownView.as_view(), name="scope-breakdown"),
    path("health/", views.HealthView.as_view(), name="health"),
    path("", include(router.urls)),
]
