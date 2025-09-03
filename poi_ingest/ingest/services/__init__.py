"""
Services package for POI data processing.

This package contains utilities for parsing, normalizing, and upserting
Point of Interest data from various sources (CSV, JSON, XML).
"""

from .normalizers import (
    coerce_to_float,
    coerce_to_float_list,
    clamp_rating,
    compute_average_rating,
    parse_coordinates,
)
from .parsers import parse_csv, parse_json, parse_xml
from .upsert import upsert_poi
from .schemas import (
    PointInPayload,
    validate_poi_record,
    safe_validate_poi_record,
    batch_validate_poi_records,
)

__all__ = [
    "coerce_to_float",
    "coerce_to_float_list",
    "clamp_rating",
    "compute_average_rating",
    "parse_coordinates",
    "parse_csv",
    "parse_json",
    "parse_xml",
    "upsert_poi",
    "PointInPayload",
    "validate_poi_record",
    "safe_validate_poi_record",
    "batch_validate_poi_records",
]
