from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = "Create default superuser if it does not exist"

    def handle(self, *args, **options):
        if not User.objects.filter(is_superuser=True).exists():
            with transaction.atomic():
                user = User.objects.create_superuser(
                    username="KiranT@1234",
                    email="kiran.tondchore@indi4.io",
                    password="KiranT@1234",
                    first_name="Kiran",
                    last_name="Tondchore",
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Superuser created: {user.email}")
                )
        else:
            self.stdout.write(self.style.WARNING("Superuser already exists"))
