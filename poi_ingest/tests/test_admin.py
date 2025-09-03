"""
Tests for Django admin functionality.
"""

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory

from ingest.admin import PointOfInterestAdmin
from ingest.models import PointOfInterest
from .factories import PointOfInterestFactory

User = get_user_model()


class TestAdminSearchAndFilters(TestCase):
    """Test admin search and filter functionality."""

    def setUp(self):
        """Set up test data and admin."""
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin = PointOfInterestAdmin(PointOfInterest, self.site)

        # Create test POIs
        self.poi1 = PointOfInterestFactory(
            external_id="admin_test_001",
            name="Admin Test Restaurant",
            category="restaurant",
            source="csv",
        )
        self.poi2 = PointOfInterestFactory(
            external_id="admin_test_002",
            name="Admin Test Hotel",
            category="hotel",
            source="json",
        )
        self.poi3 = PointOfInterestFactory(
            external_id="admin_test_003",
            name="Another Restaurant",
            category="restaurant",
            source="xml",
        )

        # Create superuser for admin access
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="testpass123"
        )

    def test_admin_search_by_internal_id(self):
        """Test exact search by internal ID works."""
        request = self.factory.get(f"/admin/ingest/pointofinterest/?q={self.poi1.id}")
        request.user = self.superuser

        # Get queryset with search
        changelist = self.admin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)

        # Should find exactly one POI
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().id, self.poi1.id)

    def test_admin_search_by_external_id(self):
        """Test exact search by external ID works."""
        request = self.factory.get("/admin/ingest/pointofinterest/?q=admin_test_001")
        request.user = self.superuser

        changelist = self.admin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)

        # Should find exactly one POI
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().external_id, "admin_test_001")

    def test_admin_category_filter_narrows_results(self):
        """Test category filter narrows results correctly."""
        request = self.factory.get(
            "/admin/ingest/pointofinterest/?category__exact=restaurant"
        )
        request.user = self.superuser

        changelist = self.admin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)

        # Should find only restaurants (2 POIs)
        self.assertEqual(queryset.count(), 2)
        for poi in queryset:
            self.assertEqual(poi.category, "restaurant")

    def test_admin_changelist_query_count(self):
        """Test that admin changelist uses efficient queries (≤ 3 queries)."""
        # Create additional test data
        PointOfInterestFactory.create_batch(10)

        request = self.factory.get("/admin/ingest/pointofinterest/")
        request.user = self.superuser

        # Test query count for changelist
        with self.assertNumQueries(3):  # Should be ≤ 3 queries
            changelist = self.admin.get_changelist_instance(request)
            queryset = changelist.get_queryset(request)

            # Force evaluation of queryset (simulate admin list rendering)
            list(queryset[:50])  # Simulate pagination

    def test_rating_count_display(self):
        """Test the custom rating_count_display method."""
        # Test POI with multiple ratings
        poi_with_ratings = PointOfInterestFactory(custom_ratings=[4.0, 5.0, 3.0])
        display = self.admin.rating_count_display(poi_with_ratings)
        self.assertEqual(display, "3 ratings")

        # Test POI with single rating
        poi_single_rating = PointOfInterestFactory(custom_ratings=[4.0])
        display = self.admin.rating_count_display(poi_single_rating)
        self.assertEqual(display, "1 rating")

        # Test POI with no ratings
        poi_no_ratings = PointOfInterestFactory(custom_ratings=[])
        display = self.admin.rating_count_display(poi_no_ratings)
        self.assertEqual(display, "No ratings")

    def test_search_help_text(self):
        """Test that search help text is properly configured."""
        help_text = self.admin.search_help_text

        # Verify help text contains guidance
        self.assertIn("Internal ID", help_text)
        self.assertIn("External ID", help_text)
        self.assertIn("exact match", help_text)
        self.assertIn("Examples:", help_text)

    def test_admin_configuration(self):
        """Test admin configuration is correct."""
        # Verify search fields
        expected_search_fields = ("=id", "=external_id", "name")
        self.assertEqual(self.admin.search_fields, expected_search_fields)

        # Verify list filters
        expected_list_filter = ("category", "source")
        self.assertEqual(self.admin.list_filter, expected_list_filter)

        # Verify list display includes rating count
        self.assertIn("rating_count_display", self.admin.list_display)

        # Verify readonly fields
        self.assertIn("avg_rating", self.admin.readonly_fields)
