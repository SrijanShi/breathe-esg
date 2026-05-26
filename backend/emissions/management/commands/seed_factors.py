from django.core.management.base import BaseCommand
from emissions.models import EmissionFactor
from emissions.factors import SEED_FACTORS


class Command(BaseCommand):
    help = "Seed the EmissionFactor table with global default factors."

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        for activity_category, scope, kg_co2e, unit, source, valid_from, notes in SEED_FACTORS:
            obj, was_created = EmissionFactor.objects.get_or_create(
                activity_category=activity_category,
                scope=scope,
                organization=None,
                valid_to=None,
                defaults={
                    "kg_co2e_per_unit": kg_co2e,
                    "unit": unit,
                    "factor_source": source,
                    "valid_from": valid_from,
                    "notes": notes,
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded emission factors: {created} created, {skipped} already existed."
            )
        )
