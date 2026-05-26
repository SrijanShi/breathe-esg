"""
Creates a demo organization + demo users for testing.
Run after seed_factors.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Organization

User = get_user_model()


class Command(BaseCommand):
    help = "Create demo organization and users."

    def handle(self, *args, **options):
        org, created = Organization.objects.get_or_create(
            slug="acme-corp",
            defaults={
                "name": "Acme Corporation",
                "fiscal_year_start_month": 1,
                "default_electricity_grid": "US_AVERAGE",
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Created organization: Acme Corporation"))
        else:
            self.stdout.write("Organization already exists: Acme Corporation")

        users = [
            ("admin@breatheesg.com", "Admin123!", "admin", "Admin"),
            ("analyst@breatheesg.com", "Analyst123!", "analyst", "Analyst"),
            ("auditor@breatheesg.com", "Auditor123!", "auditor", "Auditor"),
        ]

        for email, password, role, label in users:
            username = email.split("@")[0]
            if not User.objects.filter(email=email).exists():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    organization=org,
                    role=role,
                    first_name=label,
                    last_name="User",
                )
                self.stdout.write(self.style.SUCCESS(f"Created {label}: {email} / {password}"))
            else:
                self.stdout.write(f"User already exists: {email}")
