"""
URL configuration for ingest app API endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PointOfInterestViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(r"poi", PointOfInterestViewSet, basename="pointofinterest")

app_name = "ingest"

urlpatterns = [
    path("", include(router.urls)),
]
