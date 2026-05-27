from rest_framework.permissions import BasePermission
from core.models import UserProfile


class IsAnalystOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in (UserProfile.Role.ANALYST, UserProfile.Role.ADMIN)
        )


class IsAdminOnly(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == UserProfile.Role.ADMIN
        )


class IsAnyOrgMember(BasePermission):
    """Analysts, admins, and auditors can all read."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.organization is not None
