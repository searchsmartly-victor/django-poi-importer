"""
Tests for POI import parsers and functionality.
"""

import tempfile
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Any

import pytest
from django.test import TestCase

from ingest.models import PointOfInterest
from ingest.services.parsers import parse_csv, parse_json, parse_xml
from ingest.services.upsert import upsert_poi, batch_upsert_pois
from ingest.services.normalizers import clamp_rating, compute_average_rating
from tests.factories import PointOfInterestFactory


class TestCSVImport(TestCase):
    """Test CSV import functionality."""
    
    def test_import_csv_basic(self):
        """Test basic CSV import with 3 rows, verify created count and fields."""
        csv_content = """poi_id,poi_name,poi_category,poi_latitude,poi_longitude,poi_ratings
test_001,Test Restaurant,restaurant,40.7128,-74.0060,"{4.5,3.8,4.2}"
test_002,Test Hotel,hotel,40.7589,-73.9851,"{3.5,4.0,2.8,4.2}"
test_003,Test Museum,museum,40.7794,-73.9632,"{4.8,4.9,4.7}"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            # Parse CSV
            records = list(parse_csv(f.name))
            
            # Verify record count
            self.assertEqual(len(records), 3)
            
            # Verify first record fields
            first_record = records[0]
            self.assertEqual(first_record['external_id'], 'test_001')
            self.assertEqual(first_record['name'], 'Test Restaurant')
            self.assertEqual(first_record['category'], 'restaurant')
            self.assertEqual(first_record['source'], 'csv')
            self.assertEqual(first_record['latitude'], Decimal('40.712800'))
            self.assertEqual(first_record['longitude'], Decimal('-74.006000'))
            
            # Verify ratings parsing and average calculation
            expected_ratings = [4.5, 3.8, 4.2]
            self.assertEqual(first_record['ratings'], expected_ratings)
            
            # Import to database
            created, updated, errors = batch_upsert_pois(records)
            
            # Verify database results
            self.assertEqual(created, 3)
            self.assertEqual(updated, 0)
            self.assertEqual(errors, 0)
            
            # Verify average rating calculation
            poi = PointOfInterest.objects.get(external_id='test_001', source='csv')
            expected_avg = Decimal('4.17')  # (4.5 + 3.8 + 4.2) / 3 = 4.17
            self.assertEqual(poi.avg_rating, expected_avg)
            
        # Cleanup
        Path(f.name).unlink()


class TestJSONImport(TestCase):
    """Test JSON import functionality."""
    
    def test_import_json_array(self):
        """Test JSON import with array format."""
        json_content = """[
    {
        "id": "json_001",
        "name": "JSON Restaurant",
        "coordinates": {"latitude": 40.7128, "longitude": -74.0060},
        "category": "restaurant",
        "ratings": [4.5, 3.8, 4.2],
        "description": "A great restaurant"
    },
    {
        "id": "json_002",
        "name": "JSON Hotel", 
        "coordinates": [40.7589, -73.9851],
        "category": "hotel",
        "ratings": "3.5, 4.0, 2.8",
        "description": "Nice hotel"
    }
]"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(json_content)
            f.flush()
            
            records = list(parse_json(f.name))
            
            # Verify parsing
            self.assertEqual(len(records), 2)
            
            # Test first record (object coordinates)
            first_record = records[0]
            self.assertEqual(first_record['external_id'], 'json_001')
            self.assertEqual(first_record['source'], 'json')
            self.assertEqual(first_record['ratings'], [4.5, 3.8, 4.2])
            
            # Test second record (array coordinates + string ratings)
            second_record = records[1]
            self.assertEqual(second_record['external_id'], 'json_002')
            self.assertEqual(second_record['ratings'], [3.5, 4.0, 2.8])
            
        Path(f.name).unlink()
    
    def test_import_json_ndjson(self):
        """Test newline-delimited JSON (NDJSON) format."""
        ndjson_content = """{"id": "ndjson_001", "name": "NDJSON Restaurant", "coordinates": {"latitude": 40.7128, "longitude": -74.0060}, "category": "restaurant", "ratings": [4.0, 5.0]}
{"id": "ndjson_002", "name": "NDJSON Cafe", "coordinates": [40.7589, -73.9851], "category": "coffee-shop", "ratings": [3.5, 4.2]}
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(ndjson_content)
            f.flush()
            
            records = list(parse_json(f.name))
            
            # Verify NDJSON parsing
            self.assertEqual(len(records), 2)
            
            first_record = records[0]
            self.assertEqual(first_record['external_id'], 'ndjson_001')
            self.assertEqual(first_record['ratings'], [4.0, 5.0])
            
        Path(f.name).unlink()


class TestXMLImport(TestCase):
    """Test XML import functionality."""
    
    def test_import_xml_basic(self):
        """Test XML import with correct tag parsing."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<RECORDS>
    <DATA_RECORD>
        <pid>xml_001</pid>
        <pname>XML Restaurant</pname>
        <pcategory>restaurant</pcategory>
        <platitude>40.7128</platitude>
        <plongitude>-74.0060</plongitude>
        <pratings>4.5, 3.8, 4.2</pratings>
    </DATA_RECORD>
    <DATA_RECORD>
        <pid>xml_002</pid>
        <pname>XML Hotel</pname>
        <pcategory>hotel</pcategory>
        <platitude>40.7589</platitude>
        <plongitude>-73.9851</plongitude>
        <pratings>3.5, 4.0, 2.8, 4.2</pratings>
    </DATA_RECORD>
</RECORDS>"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            f.flush()
            
            records = list(parse_xml(f.name))
            
            # Verify parsing
            self.assertEqual(len(records), 2)
            
            # Verify first record
            first_record = records[0]
            self.assertEqual(first_record['external_id'], 'xml_001')
            self.assertEqual(first_record['name'], 'XML Restaurant')
            self.assertEqual(first_record['category'], 'restaurant')
            self.assertEqual(first_record['source'], 'xml')
            self.assertEqual(first_record['ratings'], [4.5, 3.8, 4.2])
            
        Path(f.name).unlink()


class TestRatingValidation(TestCase):
    """Test rating clamping and validation."""
    
    def test_rating_clamping_and_empty(self):
        """Test that ratings outside [0,5] are clamped and empty lists result in avg=0."""
        
        # Test rating clamping
        self.assertEqual(clamp_rating(-1.0), 0.0)
        self.assertEqual(clamp_rating(6.0), 5.0)
        self.assertEqual(clamp_rating(3.5), 3.5)
        
        # Test average computation with clamping
        ratings_with_invalid = [6.0, -1.0, 3.0, 4.0]  # Should clamp to [5.0, 0.0, 3.0, 4.0]
        expected_avg = Decimal('3.00')  # (5.0 + 0.0 + 3.0 + 4.0) / 4
        self.assertEqual(compute_average_rating(ratings_with_invalid), expected_avg)
        
        # Test empty ratings
        self.assertEqual(compute_average_rating([]), Decimal('0.00'))
        
        # Test POI creation with invalid ratings
        poi_data = {
            'external_id': 'test_invalid_ratings',
            'source': 'csv',
            'name': 'Test POI',
            'latitude': Decimal('40.7128'),
            'longitude': Decimal('-74.0060'),
            'category': 'test',
            'ratings': [6.0, -1.0, 3.0],  # Invalid ratings
            'description': 'Test POI with invalid ratings'
        }
        
        poi, created = upsert_poi(poi_data)
        self.assertTrue(created)
        
        # Verify ratings were clamped and average calculated correctly
        expected_clamped_avg = Decimal('2.67')  # (5.0 + 0.0 + 3.0) / 3 ≈ 2.67
        self.assertEqual(poi.avg_rating, expected_clamped_avg)


class TestUpsertBehavior(TestCase):
    """Test upsert functionality."""
    
    def test_upsert_updates_existing(self):
        """Test that upsert updates existing records instead of creating duplicates."""
        
        # Create initial POI
        initial_data = {
            'external_id': 'upsert_test',
            'source': 'json',
            'name': 'Original Name',
            'latitude': Decimal('40.7128'),
            'longitude': Decimal('-74.0060'),
            'category': 'restaurant',
            'ratings': [3.0, 4.0],
            'description': 'Original description'
        }
        
        poi1, created1 = upsert_poi(initial_data)
        self.assertTrue(created1)
        original_id = poi1.id
        
        # Update same POI (same external_id + source)
        updated_data = {
            'external_id': 'upsert_test',  # Same
            'source': 'json',              # Same
            'name': 'Updated Name',        # Changed
            'latitude': Decimal('41.0000'), # Changed
            'longitude': Decimal('-75.0000'), # Changed
            'category': 'hotel',           # Changed
            'ratings': [4.5, 5.0, 4.0],   # Changed
            'description': 'Updated description'  # Changed
        }
        
        poi2, created2 = upsert_poi(updated_data)
        self.assertFalse(created2)  # Should be update, not create
        self.assertEqual(poi2.id, original_id)  # Same database record
        
        # Verify all fields were updated
        self.assertEqual(poi2.name, 'Updated Name')
        self.assertEqual(poi2.latitude, Decimal('41.000000'))
        self.assertEqual(poi2.category, 'hotel')
        self.assertEqual(poi2.ratings_raw, [4.5, 5.0, 4.0])
        self.assertEqual(poi2.avg_rating, Decimal('4.50'))
        
        # Verify no duplicate was created
        total_pois = PointOfInterest.objects.filter(
            external_id='upsert_test', 
            source='json'
        ).count()
        self.assertEqual(total_pois, 1)
    
    def test_upsert_different_sources_create_separate_records(self):
        """Test that same external_id with different sources creates separate records."""
        
        base_data = {
            'external_id': 'multi_source_test',
            'name': 'Multi Source POI',
            'latitude': Decimal('40.7128'),
            'longitude': Decimal('-74.0060'),
            'category': 'restaurant',
            'ratings': [4.0],
            'description': 'Test POI'
        }
        
        # Create CSV version
        csv_data = {**base_data, 'source': 'csv'}
        poi_csv, created_csv = upsert_poi(csv_data)
        self.assertTrue(created_csv)
        
        # Create JSON version (same external_id, different source)
        json_data = {**base_data, 'source': 'json'}
        poi_json, created_json = upsert_poi(json_data)
        self.assertTrue(created_json)
        
        # Verify separate records
        self.assertNotEqual(poi_csv.id, poi_json.id)
        
        # Verify both exist
        total_count = PointOfInterest.objects.filter(
            external_id='multi_source_test'
        ).count()
        self.assertEqual(total_count, 2)
