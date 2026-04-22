from django.contrib import admin
from .models import Visitor, Department, Host, VisitorLog


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


@admin.register(Host)
class HostAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "contact_no", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "email", "contact_no"]
    list_editable = ["is_active"]
    ordering = ["name"]


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "email",
        "visit_date",
        "status",
        "host_name",
        "created_at",
    ]
    list_filter = ["status", "visit_date", "visitor_type"]
    search_fields = ["name", "email", "qr_code"]
    readonly_fields = ["qr_code", "qr_image", "created_at", "updated_at"]


@admin.register(VisitorLog)
class VisitorLogAdmin(admin.ModelAdmin):
    list_display = ["visitor", "action", "timestamp", "user"]
    list_filter = ["action", "timestamp"]
    search_fields = ["visitor__name", "action"]
