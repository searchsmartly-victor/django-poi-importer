"""
Tests for Django admin functionality.
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory
from django.test.utils import override_settings

from ingest.admin import PointOfInterestAdmin
from ingest.models import PointOfInterest
from tests.factories import PointOfInterestFactory

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
            external_id='admin_test_001',
            name='Admin Test Restaurant',
            category='restaurant',
            source='csv'
        )
        self.poi2 = PointOfInterestFactory(
            external_id='admin_test_002', 
            name='Admin Test Hotel',
            category='hotel',
            source='json'
        )
        self.poi3 = PointOfInterestFactory(
            external_id='admin_test_003',
            name='Another Restaurant',
            category='restaurant', 
            source='xml'
        )
        
        # Create superuser for admin access
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
    
    def test_admin_search_by_internal_id(self):
        """Test exact search by internal ID."""
        request = self.factory.get(f'/admin/ingest/pointofinterest/?q={self.poi1.id}')
        request.user = self.superuser
        
        # Get queryset with search
        changelist = self.admin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        
        # Should find exactly one POI
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().id, self.poi1.id)
    
    def test_admin_search_by_external_id(self):
        """Test exact search by external ID."""
        request = self.factory.get('/admin/ingest/pointofinterest/?q=admin_test_001')
        request.user = self.superuser
        
        changelist = self.admin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        
        # Should find exactly one POI
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().external_id, 'admin_test_001')
    
    def test_admin_search_by_name_partial(self):
        """Test partial search by name."""
        request = self.factory.get('/admin/ingest/pointofinterest/?q=Restaurant')
        request.user = self.superuser
        
        changelist = self.admin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        
        # Should find POIs with "Restaurant" in name
        self.assertEqual(queryset.count(), 2)  # Both restaurants
        names = [poi.name for poi in queryset]
        self.assertIn('Admin Test Restaurant', names)
        self.assertIn('Another Restaurant', names)
    
    def test_admin_category_filter(self):
        """Test category filter narrows results."""
        request = self.factory.get('/admin/ingest/pointofinterest/?category__exact=restaurant')
        request.user = self.superuser
        
        changelist = self.admin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        
        # Should find only restaurants
        self.assertEqual(queryset.count(), 2)
        for poi in queryset:
            self.assertEqual(poi.category, 'restaurant')
    
    def test_admin_source_filter(self):
        """Test source filter."""
        request = self.factory.get('/admin/ingest/pointofinterest/?source__exact=csv')
        request.user = self.superuser
        
        changelist = self.admin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        
        # Should find only CSV POIs
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().source, 'csv')
    
    @pytest.mark.django_db
    def test_admin_changelist_query_count(self):
        """Test that admin changelist uses efficient queries (≤ 3 queries)."""
        from django.test.utils import override_settings
        
        # Create more test data
        PointOfInterestFactory.create_batch(20)
        
        request = self.factory.get('/admin/ingest/pointofinterest/')
        request.user = self.superuser
        
        # Test query count for changelist
        with self.assertNumQueries(3):  # Should be ≤ 3 queries
            changelist = self.admin.get_changelist_instance(request)
            queryset = changelist.get_queryset(request)
            
            # Force evaluation of queryset
            list(queryset)
    
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
    
    def test_recompute_average_ratings_action(self):
        """Test the recompute average ratings admin action."""
        # Create POI with incorrect average
        poi = PointOfInterestFactory(
            custom_ratings=[4.0, 5.0, 3.0],  # Should avg to 4.0
            avg_rating=Decimal('2.00')  # Incorrect average
        )
        
        # Manually set incorrect average to test recomputation
        PointOfInterest.objects.filter(id=poi.id).update(avg_rating=Decimal('2.00'))
        poi.refresh_from_db()
        self.assertEqual(poi.avg_rating, Decimal('2.00'))
        
        # Create request and run admin action
        request = self.factory.post('/admin/ingest/pointofinterest/')
        request.user = self.superuser
        request._messages = []  # Mock messages framework
        
        # Run the action
        queryset = PointOfInterest.objects.filter(id=poi.id)
        self.admin.recompute_average_ratings(request, queryset)
        
        # Verify average was recomputed
        poi.refresh_from_db()
        self.assertEqual(poi.avg_rating, Decimal('4.00'))
