"""
Management command to fix database sequences for models with auto-incrementing IDs
Usage: python manage.py fix_sequences
"""

from django.core.management.base import BaseCommand
from django.db import connection, models
from visitors.models import VisitorLog


class Command(BaseCommand):
    help = "Fix PostgreSQL sequences for tables with auto-increment IDs"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Fixing database sequences...\n"))

        # Fix VisitorLog sequence
        self.fix_table_sequence("VisitorLog", VisitorLog, "visitors_visitorlog_id_seq")

        self.stdout.write(self.style.SUCCESS("\n✅ All sequences fixed successfully!"))

    def fix_table_sequence(self, model_name, model, sequence_name):
        """Fix sequence for a specific table"""
        self.stdout.write(f"Fixing {model_name}...")

        # Get the maximum ID from the model
        max_id = model.objects.all().aggregate(models.Max("id"))["id__max"]

        if max_id is None:
            self.stdout.write(f"  No records found, setting sequence to 1")
            max_id = 0
        else:
            self.stdout.write(f"  Max ID found: {max_id}")

        # Reset the sequence
        with connection.cursor() as cursor:
            try:
                next_id = (max_id or 0) + 1
                cursor.execute(f"SELECT setval('{sequence_name}', {next_id});")
                self.stdout.write(self.style.SUCCESS(f"  ✓ Sequence set to: {next_id}"))
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Failed to fix sequence: {str(e)}")
                )
