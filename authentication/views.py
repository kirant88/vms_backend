import logging
from django.contrib.auth import get_user_model, authenticate
from django.db.models import Q
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings

User = get_user_model()
logger = logging.getLogger(__name__)


def set_refresh_cookie(response, refresh_token):
    """Set refresh token as httpOnly cookie"""
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=7 * 24 * 60 * 60,  # 7 days
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
    )


class VMSLoginAPIView(TokenObtainPairView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # For VMS, we'll use username/password login
        username = request.data.get("username")
        password = request.data.get("password")

        try:
            # Look up user by email (our USERNAME_FIELD) or username
            print(f"Login attempt for: {username}")
            user = User.objects.filter(Q(email=username) | Q(username=username)).first()
            
            if user:
                print(f"User found: {user.email}, is_staff: {user.is_staff}")
                if user.check_password(password) and user.is_staff:
                    refresh = RefreshToken.for_user(user)
                    access_token = str(refresh.access_token)
                    refresh_token = str(refresh)

                    response = Response(
                        {
                            "success": True,
                            "access": access_token,
                            "user": {
                                "id": user.id,
                                "username": user.username,
                                "email": user.email,
                                "first_name": user.first_name,
                                "last_name": user.last_name,
                                "is_staff": user.is_staff,
                                "role": user.role,
                            },
                        }
                    )

                    set_refresh_cookie(response, refresh_token)
                    return response
                else:
                    return Response(
                        {
                            "success": False,
                            "message": "Invalid password or insufficient permissions",
                        },
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
            else:
                return Response(
                    {"success": False, "message": "User not found"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        except Exception as e:
            print(f"Login error: {str(e)}")
            return Response(
                {"success": False, "message": "An error occurred during login"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VMSLogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.COOKIES.get("refresh_token")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            response = Response({"success": True, "message": "Logged out successfully"})
            response.delete_cookie("refresh_token")
            return response

        except Exception as e:
            return Response(
                {"success": False, "message": "Logout failed"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class VMSTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response(
                {"success": False, "message": "No refresh token found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.data["refresh"] = refresh_token
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            new_refresh = response.data.pop("refresh", None)
            if new_refresh:
                set_refresh_cookie(response, new_refresh)

        return response


class VMSForgotPasswordAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"success": False, "message": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"{settings.FRONTEND_URL}/reset-password/{uidb64}/{token}/"

            print(f"Password reset URL for {email}: {reset_url}")

            return Response(
                {
                    "success": True,
                    "message": "Password reset link sent to your email.",
                    "reset_url": reset_url,  # Remove this in production
                },
                status=status.HTTP_200_OK,
            )

        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )


class VMSResetPasswordAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"success": False, "message": "Invalid reset link"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {"success": False, "message": "Invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_password = request.data.get("password")
        if not new_password:
            return Response(
                {"success": False, "message": "Password is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        return Response(
            {"success": True, "message": "Password reset successfully"},
            status=status.HTTP_200_OK,
        )


class VMSChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not old_password or not new_password:
            return Response(
                {
                    "success": False,
                    "message": "Both old and new passwords are required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if not user.check_password(old_password):
            return Response(
                {"success": False, "message": "Old password is incorrect"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        return Response({"success": True, "message": "Password changed successfully"})

class IsSuperAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and getattr(request.user, 'role', None) == 'superadmin'

class AdminManagementView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        admins = User.objects.filter(role__in=['admin', 'superadmin']).values(
            'id', 'username', 'email', 'first_name', 'last_name', 'role', 'created_at'
        )
        return Response({"success": True, "admins": list(admins)})

    def post(self, request):
        # Create new admin
        email = request.data.get('email')
        username = request.data.get('username')
        password = request.data.get('password')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        role = request.data.get('role', 'admin')

        if not email or not password or not username:
            return Response({"success": False, "message": "Email, username and password are required"}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({"success": False, "message": "Email already exists"}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_staff=True
        )
        return Response({"success": True, "message": "Admin created successfully"})

    def delete(self, request, admin_id):
        try:
            admin = User.objects.get(id=admin_id)
            if admin == request.user:
                return Response({"success": False, "message": "You cannot delete yourself"}, status=status.HTTP_400_BAD_REQUEST)
            
            admin.delete()
            return Response({"success": True, "message": "Admin deleted successfully"})
        except User.DoesNotExist:
            return Response({"success": False, "message": "Admin not found"}, status=status.HTTP_404_NOT_FOUND)

class AdminResetPasswordView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, admin_id):
        try:
            admin = User.objects.get(id=admin_id)
            new_password = request.data.get('password')
            
            if not new_password:
                return Response({"success": False, "message": "Password is required"}, status=status.HTTP_400_BAD_REQUEST)

            admin.set_password(new_password)
            admin.save()
            return Response({"success": True, "message": "Password reset successfully"})
        except User.DoesNotExist:
            return Response({"success": False, "message": "Admin not found"}, status=status.HTTP_404_NOT_FOUND)

