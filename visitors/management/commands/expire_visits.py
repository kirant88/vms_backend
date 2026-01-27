from django.core.management.base import BaseCommand
from django.utils import timezone
from visitors.models import Visitor, VisitorLog


class Command(BaseCommand):
    help = "Expire visits that have passed their visit date"

    def handle(self, *args, **options):
        # Get all visits that should be expired
        visits_to_expire = Visitor.objects.filter(status__in=["pending", "verified"])

        expired_count = 0

        for visit in visits_to_expire:
            if visit.should_expire():
                # Update status to expired
                visit.status = "expired"
                visit.save()

                # Create log entry
                VisitorLog.objects.create(
                    visitor=visit,
                    action="cancelled",  # Using cancelled as closest action
                    notes=f"Visit expired automatically - QR code expired at end of visit day ({visit.visit_date})",
                )

                expired_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Expired visit: {visit.name} - {visit.visit_date}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully expired {expired_count} visits")
        )
