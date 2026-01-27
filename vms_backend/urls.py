from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def api_root(request):
    """Root endpoint with API information"""
    return JsonResponse(
        {
            "message": "VMS Backend API",
            "status": "running",
            "version": "1.0.0",
            "endpoints": {
                "admin": "/admin/",
                "api": "/api/v1/",
                "authentication": "/api/v1/auth/",
                "visitors": "/api/v1/",
                "analytics": "/api/v1/analytics/",
                "documentation": "/api/schema/swagger-ui/",
            },
        }
    )


urlpatterns = [
    path("", api_root, name="api-root"),
    path("admin/", admin.site.urls),
    path("api/v1/", include("visitors.urls")),
    path("api/v1/auth/", include("authentication.urls")),
    path("api/v1/analytics/", include("analytics.urls")),
    # API Schema & Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
