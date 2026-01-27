# Create your models here.
from django.db import models
from django.conf import settings
import uuid


class Department(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Visitor(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    ]

    VISITOR_TYPE_CHOICES = [
        ("professional", "Professional"),
        ("student", "Student"),
    ]

    VISITOR_CATEGORY_CHOICES = [
        ("government", "Government"),
        ("academic", "Academic"),
        ("industry", "Industry"),
        ("other", "Other"),
    ]

    PURPOSE_CHOICES = [
        ("business_meeting", "Business Meeting"),
        ("interview", "Interview"),
        ("delivery", "Delivery"),
        ("maintenance", "Maintenance"),
        ("training", "Training"),
        ("i_factory_visit", "iFactory Visit"),
        ("i_factory_training", "iFactory Training"),
        ("other", "Other"),
    ]

    # Basic Info
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    company = models.CharField(max_length=255, blank=True)
    visitor_type = models.CharField(
        max_length=15, choices=VISITOR_TYPE_CHOICES, default="professional"
    )
    visitor_category = models.CharField(
        max_length=20, choices=VISITOR_CATEGORY_CHOICES, default="industry"
    )

    # Visit Details
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, null=True, blank=True
    )
    visit_date = models.DateField()
    visit_time = models.TimeField()

    # Host Information
    host_name = models.CharField(max_length=255, blank=True)
    host_email = models.EmailField(blank=True)
    host_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Status and Tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    qr_code = models.CharField(max_length=100, unique=True)
    qr_image = models.ImageField(upload_to="qr_codes/", blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)

    # Additional Info
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # Reschedule tracking
    is_rescheduled = models.BooleanField(default=False)
    original_visit_date = models.DateField(null=True, blank=True)
    original_visit_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.visit_date}"

    def is_qr_expired(self):
        """Check if QR code has expired (after end of visit day)"""
        from django.utils import timezone
        from datetime import datetime, time

        now = timezone.now()
        visit_date = self.visit_date

        # QR expires at end of visit day (23:59:59)
        # Create a naive datetime and then make it timezone-aware
        naive_end_of_day = datetime.combine(visit_date, time(23, 59, 59))
        end_of_visit_day = timezone.make_aware(naive_end_of_day)

        return now > end_of_visit_day

    def is_visit_day(self):
        """Check if today is the visit day"""
        from django.utils import timezone

        today = timezone.now().date()
        return today == self.visit_date

    def should_expire(self):
        """Check if visit should be marked as expired"""
        from django.utils import timezone

        today = timezone.now().date()

        # Expire if:
        # 1. Status is pending (visitor never showed up)
        # 2. Visit date has passed (it's the day after or later)
        if self.status == "pending" and self.visit_date < today:
            return True

        # Also expire verified visits that passed the visit day without checkout
        if self.status == "verified" and self.is_qr_expired():
            return True

        return False


class VisitorLog(models.Model):
    ACTION_CHOICES = [
        ("registered", "Registered"),
        ("verified", "Verified"),
        ("checked_in", "Checked In"),
        ("checked_out", "Checked Out"),
        ("cancelled", "Cancelled"),
    ]

    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name="logs")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-timestamp"]
