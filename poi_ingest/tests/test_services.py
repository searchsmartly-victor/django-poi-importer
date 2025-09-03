"""
Tests for POI services functionality.
"""

from decimal import Decimal

from django.test import TestCase
from pydantic import ValidationError

from ingest.services.normalizers import (
    coerce_to_float,
    coerce_to_float_list,
    clamp_rating,
    compute_average_rating,
    parse_coordinates,
)
from ingest.services.schemas import (
    PointInPayload,
    validate_poi_record,
    safe_validate_poi_record,
)
from ingest.services.upsert import validate_poi_payload


class TestNormalizers(TestCase):
    """Test data normalization utilities."""

    def test_coerce_to_float(self):
        """Test float coercion with various inputs."""
        # Valid inputs
        self.assertEqual(coerce_to_float("3.14"), 3.14)
        self.assertEqual(coerce_to_float(42), 42.0)
        self.assertEqual(coerce_to_float(3.14), 3.14)

        # Invalid inputs with defaults
        self.assertEqual(coerce_to_float("invalid", default=0.0), 0.0)
        self.assertEqual(coerce_to_float(None, default=1.0), 1.0)
        self.assertEqual(coerce_to_float("", default=2.0), 2.0)

    def test_coerce_to_float_list_json_format(self):
        """Test float list coercion with JSON-like format from CSV data."""
        # Test JSON-like format from actual CSV data
        json_like = "{3.0,4.0,3.0,5.0,2.0}"
        result = coerce_to_float_list(json_like)
        expected = [3.0, 4.0, 3.0, 5.0, 2.0]
        self.assertEqual(result, expected)

        # Test regular JSON array
        json_array = "[1.5, 2.5, 3.5]"
        result = coerce_to_float_list(json_array)
        expected = [1.5, 2.5, 3.5]
        self.assertEqual(result, expected)

        # Test comma-separated string
        comma_sep = "1.0, 2.0, 3.0"
        result = coerce_to_float_list(comma_sep)
        expected = [1.0, 2.0, 3.0]
        self.assertEqual(result, expected)

        # Test empty cases
        self.assertEqual(coerce_to_float_list(""), [])
        self.assertEqual(coerce_to_float_list("[]"), [])
        self.assertEqual(coerce_to_float_list("{}"), [])

    def test_clamp_rating(self):
        """Test rating clamping functionality."""
        # Valid ratings
        self.assertEqual(clamp_rating(3.5), 3.5)
        self.assertEqual(clamp_rating(0.0), 0.0)
        self.assertEqual(clamp_rating(5.0), 5.0)

        # Invalid ratings (should be clamped)
        self.assertEqual(clamp_rating(-1.0), 0.0)
        self.assertEqual(clamp_rating(6.0), 5.0)
        self.assertEqual(clamp_rating(10.0), 5.0)

    def test_compute_average_rating(self):
        """Test average rating computation."""
        # Normal case
        ratings = [4.0, 5.0, 3.0]
        expected = Decimal("4.00")
        self.assertEqual(compute_average_rating(ratings), expected)

        # Empty ratings
        self.assertEqual(compute_average_rating([]), Decimal("0.00"))

        # Ratings with clamping needed
        invalid_ratings = [6.0, -1.0, 3.0, 4.0]
        # Should clamp to [5.0, 0.0, 3.0, 4.0] = avg 3.00
        expected = Decimal("3.00")
        self.assertEqual(compute_average_rating(invalid_ratings), expected)

    def test_parse_coordinates(self):
        """Test coordinate parsing and validation."""
        # Valid coordinates
        lat, lng = parse_coordinates(40.7128, -74.0060)
        self.assertEqual(lat, Decimal("40.712800"))
        self.assertEqual(lng, Decimal("-74.006000"))

        # String coordinates
        lat, lng = parse_coordinates("40.7128", "-74.0060")
        self.assertEqual(lat, Decimal("40.712800"))
        self.assertEqual(lng, Decimal("-74.006000"))

        # Invalid coordinates
        lat, lng = parse_coordinates(200, -200)  # Out of range
        self.assertIsNone(lat)
        self.assertIsNone(lng)

        lat, lng = parse_coordinates("invalid", "invalid")
        self.assertIsNone(lat)
        self.assertIsNone(lng)


class TestPydanticSchemas(TestCase):
    """Test Pydantic schema validation."""

    def test_valid_point_payload(self):
        """Test validation of valid POI data."""
        valid_data = {
            "external_id": "test_123",
            "source": "json",
            "name": "Test POI",
            "latitude": Decimal("40.7128"),
            "longitude": Decimal("-74.0060"),
            "category": "restaurant",
            "ratings": [4.0, 5.0, 3.0],
            "description": "A test POI",
        }

        # Should validate successfully
        validated = validate_poi_record(valid_data, "test_file")
        self.assertIsInstance(validated, PointInPayload)
        self.assertEqual(validated.external_id, "test_123")
        self.assertEqual(validated.source, "json")
        self.assertEqual(len(validated.ratings), 3)

    def test_invalid_point_payload(self):
        """Test validation of invalid POI data."""
        invalid_data = {
            "external_id": "",  # Empty external_id
            "source": "invalid",  # Invalid source
            "name": "",  # Empty name
            "latitude": 200,  # Invalid latitude
            "longitude": -200,  # Invalid longitude
            "category": "",  # Empty category
            "ratings": [6.0, -1.0],  # Invalid ratings
        }

        # Should fail validation
        with self.assertRaises(ValidationError):
            validate_poi_record(invalid_data, "test_file")

        # Safe validation should return None
        result = safe_validate_poi_record(invalid_data, "test_file")
        self.assertIsNone(result)

    def test_rating_clamping_in_schema(self):
        """Test that Pydantic schema clamps invalid ratings."""
        data_with_invalid_ratings = {
            "external_id": "test_clamp",
            "source": "json",
            "name": "Test POI",
            "latitude": Decimal("40.7128"),
            "longitude": Decimal("-74.0060"),
            "category": "restaurant",
            "ratings": [6.0, -1.0, 3.0, 4.0],  # Invalid ratings
            "description": "Test",
        }

        validated = validate_poi_record(data_with_invalid_ratings, "test_file")

        # Ratings should be clamped
        expected_ratings = [5.0, 0.0, 3.0, 4.0]  # 6.0->5.0, -1.0->0.0
        self.assertEqual(validated.ratings, expected_ratings)


class TestUpsertValidation(TestCase):
    """Test upsert validation functionality."""

    def test_validate_poi_payload_valid(self):
        """Test validation of valid POI payload."""
        valid_payload = {
            "external_id": "test_valid",
            "source": "json",
            "name": "Valid POI",
            "latitude": Decimal("40.7128"),
            "longitude": Decimal("-74.0060"),
            "category": "restaurant",
            "ratings": [4.0, 5.0],
            "description": "Valid description",
        }

        errors = validate_poi_payload(valid_payload)
        self.assertEqual(len(errors), 0)

    def test_validate_poi_payload_invalid(self):
        """Test validation of invalid POI payload."""
        invalid_payload = {
            "external_id": "",  # Empty
            "source": "invalid",  # Invalid
            "name": "",  # Empty
            "latitude": 200,  # Out of range
            "longitude": None,  # Missing
            "category": "test",
            "ratings": ["invalid", 6.0],  # Invalid ratings
        }

        errors = validate_poi_payload(invalid_payload)

        # Should have multiple validation errors
        self.assertGreater(len(errors), 0)
        self.assertIn("external_id", errors)
        self.assertIn("source", errors)
        self.assertIn("name", errors)
        self.assertIn("latitude", errors)
        self.assertIn("longitude", errors)
