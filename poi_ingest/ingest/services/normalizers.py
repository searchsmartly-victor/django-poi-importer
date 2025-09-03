"""
Normalization utilities for POI data processing.

This module provides utilities to coerce data types, clamp ratings,
compute averages, and parse coordinates.
"""

import logging
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


def coerce_to_float(value: Union[str, int, float, None], default: float = 0.0) -> float:
    """
    Coerce a value to float with robust error handling.

    Args:
        value: Value to coerce (string, int, float, or None)
        default: Default value if coercion fails

    Returns:
        Float value or default if coercion fails
    """
    if value is None:
        return default

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        # Strip whitespace and handle empty strings
        value = value.strip()
        if not value:
            return default

        try:
            return float(value)
        except ValueError:
            logger.warning(
                f"Could not coerce '{value}' to float, using default {default}"
            )
            return default

    logger.warning(
        f"Unexpected type {type(value)} for value '{value}', using default {default}"
    )
    return default


def coerce_to_float_list(
    value: Union[str, List[Union[str, int, float]], None], separator: str = ","
) -> List[float]:
    """
    Coerce a value to a list of floats.

    Args:
        value: Value to coerce (string with separators, list, or None)
        separator: Separator character for string splitting

    Returns:
        List of float values, ignoring non-numeric entries
    """
    if value is None:
        return []

    if isinstance(value, list):
        result = []
        for item in value:
            try:
                float_val = coerce_to_float(item)
                result.append(float_val)
            except Exception as e:
                logger.warning(f"Skipping non-numeric item '{item}' in list: {e}")
        return result

    if isinstance(value, str):
        # Handle empty string or "[]" representation
        value = value.strip()
        if not value or value == "[]":
            return []

        # Try to parse as JSON first (for formats like "{3.0,4.0,3.0}")
        if value.startswith("{") and value.endswith("}"):
            try:
                # Convert {3.0,4.0,3.0} to [3.0,4.0,3.0] for JSON parsing
                json_str = value.replace("{", "[").replace("}", "]")
                import json

                parsed_list = json.loads(json_str)
                if isinstance(parsed_list, list):
                    result = []
                    for item in parsed_list:
                        try:
                            float_val = coerce_to_float(item)
                            result.append(float_val)
                        except Exception as e:
                            logger.warning(
                                f"Skipping non-numeric item '{item}' in JSON array: {e}"
                            )
                    return result
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON-like rating format: {value}")

        # Try regular JSON array parsing
        if value.startswith("[") and value.endswith("]"):
            try:
                import json

                parsed_list = json.loads(value)
                if isinstance(parsed_list, list):
                    result = []
                    for item in parsed_list:
                        try:
                            float_val = coerce_to_float(item)
                            result.append(float_val)
                        except Exception as e:
                            logger.warning(
                                f"Skipping non-numeric item '{item}' in JSON array: {e}"
                            )
                    return result
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON array: {value}")

        # Remove brackets if present for comma-separated parsing
        value = re.sub(r"^\[|\]$", "", value)
        value = re.sub(r"^\{|\}$", "", value)

        # Split by separator and process each item
        result = []
        items = value.split(separator)

        for item in items:
            item = item.strip()
            if item:
                try:
                    float_val = coerce_to_float(item)
                    result.append(float_val)
                except Exception as e:
                    logger.warning(f"Skipping non-numeric rating '{item}': {e}")

        return result

    logger.warning(f"Could not coerce {type(value)} to float list: {value}")
    return []


def clamp_rating(rating: float, min_val: float = 0.0, max_val: float = 5.0) -> float:
    """
    Clamp a rating value to the specified range.

    Args:
        rating: Rating value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Clamped rating value
    """
    if rating < min_val:
        logger.warning(
            f"Rating {rating} below minimum {min_val}, clamping to {min_val}"
        )
        return min_val
    elif rating > max_val:
        logger.warning(
            f"Rating {rating} above maximum {max_val}, clamping to {max_val}"
        )
        return max_val
    return rating


def compute_average_rating(ratings: List[float]) -> Decimal:
    """
    Compute the average rating from a list of ratings.

    Args:
        ratings: List of rating values

    Returns:
        Average rating rounded to 2 decimal places, or 0.00 if no ratings
    """
    if not ratings:
        return Decimal("0.00")

    # Clamp all ratings to valid range
    clamped_ratings = [clamp_rating(rating) for rating in ratings]

    # Calculate average
    average = sum(clamped_ratings) / len(clamped_ratings)

    # Round to 2 decimal places
    decimal_avg = Decimal(str(average)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    return decimal_avg


def parse_coordinates(
    latitude: Union[str, int, float, None], longitude: Union[str, int, float, None]
) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """
    Parse and validate coordinate values.

    Args:
        latitude: Latitude value to parse
        longitude: Longitude value to parse

    Returns:
        Tuple of (latitude, longitude) as Decimal objects, or (None, None) if invalid
    """
    try:
        lat_float = coerce_to_float(latitude)
        lon_float = coerce_to_float(longitude)

        # Validate coordinate ranges
        if not (-90 <= lat_float <= 90):
            logger.warning(f"Invalid latitude {lat_float}, must be between -90 and 90")
            return None, None

        if not (-180 <= lon_float <= 180):
            logger.warning(
                f"Invalid longitude {lon_float}, must be between -180 and 180"
            )
            return None, None

        # Convert to Decimal for precision
        lat_decimal = Decimal(str(lat_float)).quantize(Decimal("0.000001"))
        lon_decimal = Decimal(str(lon_float)).quantize(Decimal("0.000001"))

        return lat_decimal, lon_decimal

    except Exception as e:
        logger.error(f"Error parsing coordinates lat={latitude}, lon={longitude}: {e}")
        return None, None


def normalize_string(value: Union[str, None], default: str = "") -> str:
    """
    Normalize a string value by stripping whitespace and handling None.

    Args:
        value: String value to normalize
        default: Default value if input is None or empty

    Returns:
        Normalized string value
    """
    if value is None:
        return default

    if isinstance(value, str):
        normalized = value.strip()
        return normalized if normalized else default

    # Convert non-string values to string
    try:
        return str(value).strip()
    except Exception as e:
        logger.warning(f"Could not normalize value '{value}' to string: {e}")
        return default
