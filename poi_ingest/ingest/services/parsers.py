"""
Parser utilities for different POI data formats.

This module provides parsers for CSV, JSON, and XML files containing
Point of Interest data.
"""

import csv
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Any, Union

from .normalizers import (
    coerce_to_float_list,
    normalize_string,
    parse_coordinates,
)
from .schemas import safe_validate_poi_record

logger = logging.getLogger(__name__)


def parse_csv(file_path: Union[str, Path]) -> Iterable[Dict[str, Any]]:
    """
    Parse CSV file containing POI data.

    Expected CSV columns:
    - poi_id: External ID
    - poi_name: POI name
    - poi_latitude: Latitude coordinate
    - poi_longitude: Longitude coordinate
    - poi_category: POI category
    - poi_ratings: Ratings as "1, 3, 4.5" or "[]"/empty

    Args:
        file_path: Path to CSV file

    Yields:
        Dict with normalized POI data
    """
    file_path = Path(file_path)
    logger.info(f"Parsing CSV file: {file_path}")

    if not file_path.exists():
        logger.error(f"CSV file not found: {file_path}")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):  # Start at 2 for header
                try:
                    # Extract and validate required fields
                    external_id = normalize_string(row.get("poi_id"))
                    if not external_id:
                        logger.warning(f"Row {row_num}: Missing poi_id, skipping")
                        continue

                    name = normalize_string(row.get("poi_name"))
                    if not name:
                        logger.warning(f"Row {row_num}: Missing poi_name, skipping")
                        continue

                    # Parse coordinates
                    latitude, longitude = parse_coordinates(
                        row.get("poi_latitude"), row.get("poi_longitude")
                    )
                    if latitude is None or longitude is None:
                        logger.warning(f"Row {row_num}: Invalid coordinates, skipping")
                        continue

                    # Parse ratings
                    ratings_raw = row.get("poi_ratings", "")
                    ratings = coerce_to_float_list(ratings_raw)

                    # Build normalized record
                    record_data = {
                        "external_id": external_id,
                        "name": name,
                        "latitude": latitude,
                        "longitude": longitude,
                        "category": normalize_string(
                            row.get("poi_category"), "Unknown"
                        ),
                        "ratings": ratings,
                        "description": normalize_string(row.get("poi_description", "")),
                        "source": "csv",
                    }

                    # Validate using Pydantic schema
                    validated_record = safe_validate_poi_record(
                        record_data, f"{file_path}:row_{row_num}"
                    )
                    if validated_record is not None:
                        # Convert back to dict for compatibility
                        yield validated_record.model_dump()
                    else:
                        logger.warning(f"Skipping invalid CSV record at row {row_num}")

                except Exception as e:
                    logger.error(f"Error parsing CSV row {row_num} in {file_path}: {e}")
                    continue

    except Exception as e:
        logger.error(f"Error reading CSV file {file_path}: {e}")


def parse_json(file_path: Union[str, Path]) -> Iterable[Dict[str, Any]]:
    """
    Parse JSON file containing POI data.

    Expected JSON structure:
    - Single object: {id, name, coordinates[latitude, longitude], category, ratings, description}
    - Array of objects: [{...}, {...}]
    - Newline-delimited JSON: One object per line

    Args:
        file_path: Path to JSON file

    Yields:
        Dict with normalized POI data
    """
    file_path = Path(file_path)
    logger.info(f"Parsing JSON file: {file_path}")

    if not file_path.exists():
        logger.error(f"JSON file not found: {file_path}")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            logger.warning(f"Empty JSON file: {file_path}")
            return

        # Try to parse as regular JSON first
        try:
            data = json.loads(content)

            # Handle single object
            if isinstance(data, dict):
                record = _parse_json_object(data, file_path)
                if record:
                    yield record

            # Handle array of objects
            elif isinstance(data, list):
                for idx, item in enumerate(data):
                    if isinstance(item, dict):
                        record = _parse_json_object(item, file_path, idx)
                        if record:
                            yield record
                    else:
                        logger.warning(f"Non-object item at index {idx} in {file_path}")

            else:
                logger.error(f"Unexpected JSON structure in {file_path}: {type(data)}")

        except json.JSONDecodeError:
            # Try parsing as newline-delimited JSON
            logger.info(f"Attempting to parse {file_path} as newline-delimited JSON")

            for line_num, line in enumerate(content.splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        record = _parse_json_object(obj, file_path, line_num)
                        if record:
                            yield record
                    else:
                        logger.warning(f"Non-object on line {line_num} in {file_path}")

                except json.JSONDecodeError as e:
                    logger.error(
                        f"JSON parse error on line {line_num} in {file_path}: {e}"
                    )
                    continue

    except Exception as e:
        logger.error(f"Error reading JSON file {file_path}: {e}")


def _parse_json_object(
    obj: Dict[str, Any], file_path: Path, index: int = 0
) -> Dict[str, Any]:
    """
    Parse a single JSON object into normalized POI data.

    Args:
        obj: JSON object to parse
        file_path: Source file path for logging
        index: Object index for logging

    Returns:
        Normalized POI record or None if invalid
    """
    try:
        # Extract and validate required fields
        external_id = normalize_string(obj.get("id"))
        if not external_id:
            logger.warning(f"Object {index} in {file_path}: Missing id, skipping")
            return None

        name = normalize_string(obj.get("name"))
        if not name:
            logger.warning(f"Object {index} in {file_path}: Missing name, skipping")
            return None

        # Parse coordinates
        coordinates = obj.get("coordinates", {})
        if isinstance(coordinates, list) and len(coordinates) >= 2:
            # Handle [latitude, longitude] format
            latitude, longitude = parse_coordinates(coordinates[0], coordinates[1])
        elif isinstance(coordinates, dict):
            # Handle {latitude: ..., longitude: ...} format
            latitude, longitude = parse_coordinates(
                coordinates.get("latitude"), coordinates.get("longitude")
            )
        else:
            logger.warning(f"Object {index} in {file_path}: Invalid coordinates format")
            return None

        if latitude is None or longitude is None:
            logger.warning(
                f"Object {index} in {file_path}: Invalid coordinates, skipping"
            )
            return None

        # Parse ratings
        ratings_raw = obj.get("ratings", [])
        if isinstance(ratings_raw, str):
            ratings = coerce_to_float_list(ratings_raw)
        else:
            ratings = coerce_to_float_list(ratings_raw)

        # Build normalized record
        record_data = {
            "external_id": external_id,
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "category": normalize_string(obj.get("category"), "Unknown"),
            "ratings": ratings,
            "description": normalize_string(obj.get("description", "")),
            "source": "json",
        }

        # Validate using Pydantic schema
        validated_record = safe_validate_poi_record(
            record_data, f"{file_path}:object_{index}"
        )
        if validated_record is not None:
            return validated_record.model_dump()
        else:
            logger.warning(f"Skipping invalid JSON object at index {index}")
            return None

    except Exception as e:
        logger.error(f"Error parsing JSON object {index} in {file_path}: {e}")
        return None


def parse_xml(file_path: Union[str, Path]) -> Iterable[Dict[str, Any]]:
    """
    Parse XML file containing POI data.

    Expected XML structure with tags:
    - pid: External ID
    - pname: POI name
    - platitude: Latitude coordinate
    - plongitude: Longitude coordinate
    - pcategory: POI category
    - pratings: Ratings as "1, 4, 5"
    - pdescription: Description (optional)

    Args:
        file_path: Path to XML file

    Yields:
        Dict with normalized POI data
    """
    file_path = Path(file_path)
    logger.info(f"Parsing XML file: {file_path}")

    if not file_path.exists():
        logger.error(f"XML file not found: {file_path}")
        return

    try:
        # Try to parse XML with recovery for malformed content
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError as e:
            logger.error(f"XML parse error in {file_path}: {e}")
            # Try to read and clean the XML content
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Basic XML cleaning - remove problematic characters and fix common issues
                import re

                # Remove control characters except tab, newline, carriage return
                content = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", content)

                # Escape unescaped ampersands that aren't part of entities
                content = re.sub(r"&(?![a-zA-Z0-9#]+;)", "&amp;", content)

                # Try parsing the cleaned content
                root = ET.fromstring(content)
                logger.info(f"Successfully parsed XML after cleaning: {file_path}")
            except Exception as clean_error:
                logger.error(
                    f"Failed to parse XML even after cleaning {file_path}: {clean_error}"
                )
                return

        # Find all POI elements (try common tag names)
        poi_elements = []

        # Try different possible structures
        if root.tag in ["poi", "pois", "point_of_interest"]:
            poi_elements = [root]
        else:
            # Look for POI elements as children - check actual data structure first
            poi_elements.extend(root.findall(".//DATA_RECORD"))  # For actual XML data
            poi_elements.extend(root.findall(".//poi"))
            poi_elements.extend(root.findall(".//point_of_interest"))
            poi_elements.extend(root.findall(".//item"))

            # If no specific POI tags found, treat each child as a POI
            if not poi_elements:
                poi_elements = list(root)

        for idx, poi_elem in enumerate(poi_elements):
            try:
                # Extract and validate required fields
                external_id = normalize_string(
                    _get_xml_text(poi_elem, ["pid", "id", "external_id"])
                )
                if not external_id:
                    logger.warning(
                        f"POI element {idx} in {file_path}: Missing pid/id, skipping"
                    )
                    continue

                name = normalize_string(_get_xml_text(poi_elem, ["pname", "name"]))
                if not name:
                    logger.warning(
                        f"POI element {idx} in {file_path}: Missing pname/name, skipping"
                    )
                    continue

                # Parse coordinates
                latitude, longitude = parse_coordinates(
                    _get_xml_text(poi_elem, ["platitude", "latitude"]),
                    _get_xml_text(poi_elem, ["plongitude", "longitude"]),
                )
                if latitude is None or longitude is None:
                    logger.warning(
                        f"POI element {idx} in {file_path}: Invalid coordinates, skipping"
                    )
                    continue

                # Parse ratings
                ratings_raw = _get_xml_text(poi_elem, ["pratings", "ratings"], "")
                ratings = coerce_to_float_list(ratings_raw)

                # Build normalized record
                record_data = {
                    "external_id": external_id,
                    "name": name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "category": normalize_string(
                        _get_xml_text(poi_elem, ["pcategory", "category"]), "Unknown"
                    ),
                    "ratings": ratings,
                    "description": normalize_string(
                        _get_xml_text(poi_elem, ["pdescription", "description"], "")
                    ),
                    "source": "xml",
                }

                # Validate using Pydantic schema
                validated_record = safe_validate_poi_record(
                    record_data, f"{file_path}:element_{idx}"
                )
                if validated_record is not None:
                    yield validated_record.model_dump()
                else:
                    logger.warning(f"Skipping invalid XML element at index {idx}")

            except Exception as e:
                logger.error(f"Error parsing XML POI element {idx} in {file_path}: {e}")
                continue

    except ET.ParseError as e:
        logger.error(f"XML parse error in {file_path}: {e}")
    except Exception as e:
        logger.error(f"Error reading XML file {file_path}: {e}")


def _get_xml_text(
    element: ET.Element, tag_names: List[str], default: str = None
) -> str:
    """
    Get text content from XML element trying multiple tag names.

    Args:
        element: XML element to search
        tag_names: List of tag names to try
        default: Default value if no tag found

    Returns:
        Text content or default value
    """
    for tag_name in tag_names:
        child = element.find(tag_name)
        if child is not None and child.text is not None:
            return child.text.strip()

    return default
