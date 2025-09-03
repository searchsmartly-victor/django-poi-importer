"""
URL configuration for poi_ingest project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.shortcuts import redirect
from django.conf import settings


def health_check(request):
    """Simple health check endpoint."""
    return JsonResponse({"status": "ok"})


def home_redirect(request):
    """Redirect root URL to admin interface."""
    return redirect('/admin/')


urlpatterns = [
    path("", home_redirect, name="home"),
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health"),
    path("api/", include("ingest.urls")),
    path("api/auth/", include("rest_framework.urls", namespace="rest_framework")),
]

# Add debug toolbar URLs in development
if settings.DEBUG:
    try:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
