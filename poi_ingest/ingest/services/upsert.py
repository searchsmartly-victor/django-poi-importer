"""
Upsert utilities for POI data.

This module provides functionality to create or update PointOfInterest
records based on external_id and source.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Tuple, List, Union

from django.db import transaction

from ..models import PointOfInterest
from .normalizers import compute_average_rating, normalize_string
from .schemas import PointInPayload

logger = logging.getLogger(__name__)


def upsert_poi(
    payload: Union[Dict[str, Any], PointInPayload],
) -> Tuple[PointOfInterest, bool]:
    """
    Create or update a PointOfInterest record.

    Args:
        payload: Dictionary or PointInPayload containing POI data

    Returns:
        Tuple of (PointOfInterest instance, created: bool)

    Raises:
        ValueError: If required fields are missing or invalid
    """
    # Handle both dict and Pydantic model inputs
    if isinstance(payload, PointInPayload):
        # Already validated Pydantic model
        external_id = payload.external_id
        source = payload.source
        name = payload.name
        latitude = payload.latitude
        longitude = payload.longitude
        category = payload.category
        description = payload.description
        ratings = payload.ratings
    else:
        # Legacy dict input - validate required fields
        external_id = normalize_string(payload.get("external_id"))
        if not external_id:
            raise ValueError("external_id is required")

        source = normalize_string(payload.get("source"))
        if source not in ["csv", "json", "xml"]:
            raise ValueError(
                f"Invalid source '{source}', must be one of: csv, json, xml"
            )

        name = normalize_string(payload.get("name"))
        if not name:
            raise ValueError("name is required")

        latitude = payload.get("latitude")
        longitude = payload.get("longitude")
        if latitude is None or longitude is None:
            raise ValueError("latitude and longitude are required")

        # Convert to Decimal if not already
        if not isinstance(latitude, Decimal):
            try:
                latitude = Decimal(str(latitude))
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid latitude value: {e}")

        if not isinstance(longitude, Decimal):
            try:
                longitude = Decimal(str(longitude))
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid longitude value: {e}")

        # Process optional fields
        category = normalize_string(payload.get("category"), "Unknown")
        description = normalize_string(payload.get("description", ""))
        ratings = payload.get("ratings", [])

    # Ensure ratings is a list
    if not isinstance(ratings, list):
        logger.warning(f"Expected ratings to be a list, got {type(ratings)}: {ratings}")
        ratings = []

    # Compute average rating
    avg_rating = compute_average_rating(ratings)

    logger.info(f"Upserting POI: {external_id} ({source}) - {name}")

    try:
        with transaction.atomic():
            # Try to get existing record
            poi, created = PointOfInterest.objects.get_or_create(
                external_id=external_id,
                source=source,
                defaults={
                    "name": name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "category": category,
                    "ratings_raw": ratings,
                    "avg_rating": avg_rating,
                    "description": description,
                },
            )

            # If record exists, update all fields
            if not created:
                logger.info(f"Updating existing POI: {poi.id} - {poi.name}")

                poi.name = name
                poi.latitude = latitude
                poi.longitude = longitude
                poi.category = category
                poi.ratings_raw = ratings
                poi.avg_rating = avg_rating
                poi.description = description

                # Save without calling full_clean to avoid validation issues
                poi.save(
                    update_fields=[
                        "name",
                        "latitude",
                        "longitude",
                        "category",
                        "ratings_raw",
                        "avg_rating",
                        "description",
                    ]
                )

                logger.info(
                    f"Updated POI {poi.id}: {name} with {len(ratings)} ratings (avg: {avg_rating})"
                )
            else:
                logger.info(
                    f"Created new POI {poi.id}: {name} with {len(ratings)} ratings (avg: {avg_rating})"
                )

            return poi, created

    except Exception as e:
        logger.error(f"Error upserting POI {external_id} ({source}): {e}")
        raise


def batch_upsert_pois(payloads: List[Dict[str, Any]]) -> Tuple[int, int, int]:
    """
    Batch upsert multiple POI records.

    Args:
        payloads: List of POI data dictionaries

    Returns:
        Tuple of (created_count, updated_count, error_count)
    """
    created_count = 0
    updated_count = 0
    error_count = 0

    logger.info(f"Starting batch upsert of {len(payloads)} POI records")

    for idx, payload in enumerate(payloads):
        try:
            poi, created = upsert_poi(payload)

            if created:
                created_count += 1
            else:
                updated_count += 1

        except Exception as e:
            error_count += 1
            external_id = payload.get("external_id", "unknown")
            source = payload.get("source", "unknown")
            logger.error(
                f"Error processing POI {idx + 1} ({external_id}/{source}): {e}"
            )
            continue

    logger.info(
        f"Batch upsert completed: {created_count} created, "
        f"{updated_count} updated, {error_count} errors"
    )

    return created_count, updated_count, error_count


def validate_poi_payload(payload: Dict[str, Any]) -> Dict[str, str]:
    """
    Validate a POI payload and return validation errors.

    Args:
        payload: POI data dictionary to validate

    Returns:
        Dictionary of field -> error message for invalid fields
    """
    errors = {}

    # Check required fields
    if not normalize_string(payload.get("external_id")):
        errors["external_id"] = "This field is required"

    source = normalize_string(payload.get("source"))
    if not source:
        errors["source"] = "This field is required"
    elif source not in ["csv", "json", "xml"]:
        errors["source"] = f'Invalid source "{source}", must be one of: csv, json, xml'

    if not normalize_string(payload.get("name")):
        errors["name"] = "This field is required"

    # Check coordinates
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")

    if latitude is None:
        errors["latitude"] = "This field is required"
    else:
        try:
            lat_decimal = Decimal(str(latitude))
            if not (-90 <= lat_decimal <= 90):
                errors["latitude"] = "Latitude must be between -90 and 90"
        except (ValueError, TypeError):
            errors["latitude"] = "Invalid latitude value"

    if longitude is None:
        errors["longitude"] = "This field is required"
    else:
        try:
            lon_decimal = Decimal(str(longitude))
            if not (-180 <= lon_decimal <= 180):
                errors["longitude"] = "Longitude must be between -180 and 180"
        except (ValueError, TypeError):
            errors["longitude"] = "Invalid longitude value"

    # Validate ratings if present
    ratings = payload.get("ratings")
    if ratings is not None:
        if not isinstance(ratings, list):
            errors["ratings"] = "Ratings must be a list"
        else:
            for idx, rating in enumerate(ratings):
                try:
                    rating_float = float(rating)
                    if not (0 <= rating_float <= 5):
                        errors["ratings"] = (
                            f"Rating at index {idx} must be between 0 and 5"
                        )
                        break
                except (ValueError, TypeError):
                    errors["ratings"] = f"Rating at index {idx} is not a valid number"
                    break

    return errors
