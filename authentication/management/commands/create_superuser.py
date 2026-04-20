from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = "Create or update default superadmin"

    def handle(self, *args, **options):
        email = "kiran.tondchore@indi4.io"
        username = "kiran.tondchore@indi4.io"
        password = "KiranT@1234"

        with transaction.atomic():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": username,
                    "first_name": "Kiran",
                    "last_name": "Tondchore",
                    "role": "superadmin",
                    "is_verified": True,
                },
            )

            if created:
                user.set_password(password)
                user.is_superuser = True
                user.is_staff = True
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f"Superadmin created: {user.email}")
                )
                return

            updated = False
            if user.username != username:
                user.username = username
                updated = True
            if user.first_name != "Kiran":
                user.first_name = "Kiran"
                updated = True
            if user.last_name != "Tondchore":
                user.last_name = "Tondchore"
                updated = True
            if user.role != "superadmin":
                user.role = "superadmin"
                updated = True
            if not user.is_verified:
                user.is_verified = True
                updated = True
            if not user.is_superuser:
                user.is_superuser = True
                updated = True
            if not user.is_staff:
                user.is_staff = True
                updated = True

            user.set_password(password)
            updated = True

            if updated:
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f"Superadmin updated: {user.email}")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Superadmin already correct: {user.email}")
                )
