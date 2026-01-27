from django.conf import settings


def set_refresh_cookie(response, refresh_token):
    """Set refresh token as httpOnly cookie"""
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds(),
        httponly=True,
        secure=not settings.DEBUG,  # Use secure cookies in production
        samesite="Lax",
    )
