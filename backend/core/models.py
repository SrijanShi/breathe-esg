import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    fiscal_year_start_month = models.PositiveSmallIntegerField(
        default=1,
        help_text="1=January, 4=April (common for UK companies)",
    )
    default_electricity_grid = models.CharField(
        max_length=64,
        default="US_AVERAGE",
        help_text="eGRID subregion code for Scope 2 location-based factor lookup",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserProfile(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="members",
        null=True,
        blank=True,
    )

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        ANALYST = "analyst", "Analyst"
        AUDITOR = "auditor", "Auditor (read-only)"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ANALYST)

    class Meta:
        verbose_name = "User"

    def __str__(self):
        return f"{self.email} ({self.organization})"
