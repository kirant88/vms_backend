from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.analytics_dashboard, name="analytics-dashboard"),
    path("visitor-trends/", views.visitor_trends, name="visitor-trends"),
    path("department-stats/", views.department_stats, name="department-stats"),
    path("hourly-stats/", views.hourly_stats, name="hourly-stats"),
]
