from django.urls import path
from .views import (
    VMSLoginAPIView,
    VMSLogoutAPIView,
    VMSTokenRefreshView,
    VMSChangePasswordAPIView,
    VMSForgotPasswordAPIView,
    VMSResetPasswordAPIView,
    AdminManagementView,
    AdminResetPasswordView,
)

urlpatterns = [
    path("login/", VMSLoginAPIView.as_view(), name="vms-login"),
    path("logout/", VMSLogoutAPIView.as_view(), name="vms-logout"),
    path("refresh/", VMSTokenRefreshView.as_view(), name="vms-refresh"),
    path(
        "change-password/",
        VMSChangePasswordAPIView.as_view(),
        name="vms-change-password",
    ),
    path(
        "forgot-password/",
        VMSForgotPasswordAPIView.as_view(),
        name="vms-forgot-password",
    ),
    path(
        "reset-password/<str:uidb64>/<str:token>/",
        VMSResetPasswordAPIView.as_view(),
        name="vms-reset-password",
    ),
    path("admins/", AdminManagementView.as_view(), name="vms-admins"),
    path("admins/<int:admin_id>/", AdminManagementView.as_view(), name="vms-admin-detail"),
    path("admins/<int:admin_id>/reset-password/", AdminResetPasswordView.as_view(), name="vms-admin-reset-password"),
]
