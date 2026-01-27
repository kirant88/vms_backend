from django.urls import path
from . import views

urlpatterns = [
    path("departments/", views.DepartmentListView.as_view(), name="department-list"),
    path(
        "visitors/", views.VisitorListCreateView.as_view(), name="visitor-list-create"
    ),
    path(
        "visitors/<uuid:pk>/", views.VisitorDetailView.as_view(), name="visitor-detail"
    ),
    path("visitors/search/", views.VisitorSearchView.as_view(), name="visitor-search"),
    path("verify-qr/", views.verify_qr_code, name="verify-qr"),
    path("dashboard-stats/", views.dashboard_stats, name="dashboard-stats"),
    path("export/excel/", views.export_visitors_excel, name="export-visitors-excel"),
    path(
        "visitors/<uuid:visitor_id>/resend-email/",
        views.resend_visitor_email,
        name="resend-visitor-email",
    ),
    path(
        "visitors/<uuid:visitor_id>/delete/",
        views.delete_visitor,
        name="delete-visitor",
    ),
    path(
        "check-slot-availability/",
        views.check_slot_availability_api,
        name="check-slot-availability",
    ),
    path(
        "available-slots/",
        views.get_available_slots_api,
        name="get-available-slots",
    ),
    path(
        "visitors/<uuid:visitor_id>/reschedule/",
        views.reschedule_visitor,
        name="reschedule-visitor",
    ),
    path(
        "visitors/<uuid:visitor_id>/complete/",
        views.manual_complete_visit,
        name="manual-complete-visit",
    ),
    path(
        "hosts/",
        views.get_hosts,
        name="get-hosts",
    ),
    path(
        "bulk/template/download/",
        views.download_bulk_template,
        name="download-bulk-template",
    ),
    path(
        "bulk/upload/",
        views.bulk_upload_visitors,
        name="bulk-upload-visitors",
    ),
]
