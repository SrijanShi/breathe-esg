from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Organization, UserProfile


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "default_electricity_grid", "created_at"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(UserProfile)
class UserProfileAdmin(UserAdmin):
    list_display = ["email", "username", "organization", "role", "is_active"]
    list_filter = ["role", "organization"]
    fieldsets = UserAdmin.fieldsets + (
        ("Breathe ESG", {"fields": ("organization", "role")}),
    )
