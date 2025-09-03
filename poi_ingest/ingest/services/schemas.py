"""
Pydantic schemas for POI data validation.

This module defines data validation schemas using Pydantic for robust
type checking and data validation of Point of Interest records.
"""

import logging
from decimal import Decimal
from typing import List, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator
from pydantic.types import condecimal, confloat, constr

logger = logging.getLogger(__name__)

# Type aliases for coordinates and ratings
Latitude = condecimal(
    ge=Decimal("-90"), le=Decimal("90"), max_digits=9, decimal_places=6
)
Longitude = condecimal(
    ge=Decimal("-180"), le=Decimal("180"), max_digits=9, decimal_places=6
)
Rating = confloat(ge=0.0, le=5.0)


class PointInPayload(BaseModel):
    """
    Pydantic model for validating Point of Interest data payloads.

    This model ensures that all POI data meets the required constraints
    before being processed and stored in the database.
    """

    external_id: constr(strip_whitespace=True, min_length=1, max_length=128) = Field(
        ..., description="External identifier for the POI, must be unique per source"
    )

    source: Literal["csv", "json", "xml"] = Field(..., description="Data source type")

    name: constr(strip_whitespace=True, min_length=1, max_length=255) = Field(
        ..., description="Name of the Point of Interest"
    )

    latitude: Latitude = Field(
        ..., description="Latitude coordinate (-90 to 90 degrees)"
    )

    longitude: Longitude = Field(
        ..., description="Longitude coordinate (-180 to 180 degrees)"
    )

    category: constr(strip_whitespace=True, min_length=1, max_length=64) = Field(
        ..., description="Category of the POI"
    )

    ratings: List[Rating] = Field(
        default=[], description="List of ratings (0.0 to 5.0)"
    )

    description: str = Field(default="", description="Optional description of the POI")

    @field_validator("ratings")
    @classmethod
    def validate_ratings(cls, v: List[float]) -> List[float]:
        """
        Validate ratings list and clamp values if needed.
        """
        if not isinstance(v, list):
            raise ValueError("Ratings must be a list")

        validated_ratings = []
        for i, rating in enumerate(v):
            if not isinstance(rating, (int, float)):
                logger.warning(f"Skipping non-numeric rating at index {i}: {rating}")
                continue

            # Clamp rating to valid range
            if rating < 0:
                logger.warning(f"Rating {rating} below minimum, clamping to 0.0")
                rating = 0.0
            elif rating > 5:
                logger.warning(f"Rating {rating} above maximum, clamping to 5.0")
                rating = 5.0

            validated_ratings.append(float(rating))

        return validated_ratings

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """
        Validate and normalize description field.
        """
        if v is None:
            return ""

        if isinstance(v, str):
            # Limit description length to prevent database issues
            max_length = 1000
            if len(v) > max_length:
                logger.warning(
                    f"Description too long ({len(v)} chars), truncating to {max_length}"
                )
                return v[:max_length]
            return v

        # Convert non-string values
        try:
            return str(v)
        except Exception:
            logger.warning(f"Could not convert description to string: {v}")
            return ""

    def model_post_init(self, __context) -> None:
        """
        Post-initialization validation and logging.
        """
        # Log validation success for debugging
        logger.debug(
            f"Validated POI: {self.external_id} ({self.source}) - "
            f"{self.name} with {len(self.ratings)} ratings"
        )


def validate_poi_record(data: dict, source_file: str = "unknown") -> PointInPayload:
    """
    Validate a POI record using Pydantic schema.

    Args:
        data: Raw POI data dictionary
        source_file: Source file name for logging context

    Returns:
        Validated PointInPayload instance

    Raises:
        ValidationError: If validation fails
    """
    try:
        # Create and validate the Pydantic model
        validated_poi = PointInPayload(**data)
        return validated_poi

    except ValidationError as e:
        # Log validation errors with context
        external_id = data.get("external_id", "unknown")
        logger.error(
            f"Validation failed for POI {external_id} in {source_file}: "
            f"{e.error_count()} errors"
        )

        # Log individual validation errors
        for error in e.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            logger.error(
                f"  Field '{field}': {error['msg']} "
                f"(input: {error.get('input', 'N/A')})"
            )

        raise


def safe_validate_poi_record(
    data: dict, source_file: str = "unknown"
) -> PointInPayload:
    """
    Safely validate a POI record, returning None if validation fails.

    Args:
        data: Raw POI data dictionary
        source_file: Source file name for logging context

    Returns:
        Validated PointInPayload instance or None if validation fails
    """
    try:
        return validate_poi_record(data, source_file)
    except ValidationError:
        # Validation error already logged in validate_poi_record
        return None
    except Exception as e:
        external_id = data.get("external_id", "unknown")
        logger.error(
            f"Unexpected error validating POI {external_id} in {source_file}: {e}"
        )
        return None


class POIBatchValidationResult(BaseModel):
    """
    Result of batch POI validation.
    """

    valid_records: List[PointInPayload] = Field(
        default=[], description="List of successfully validated POI records"
    )

    invalid_count: int = Field(
        default=0, description="Number of records that failed validation"
    )

    total_processed: int = Field(
        default=0, description="Total number of records processed"
    )

    @property
    def validation_rate(self) -> float:
        """
        Calculate the validation success rate as a percentage.
        """
        if self.total_processed == 0:
            return 0.0
        return (len(self.valid_records) / self.total_processed) * 100


def batch_validate_poi_records(
    records: List[dict], source_file: str = "unknown"
) -> POIBatchValidationResult:
    """
    Validate a batch of POI records.

    Args:
        records: List of raw POI data dictionaries
        source_file: Source file name for logging context

    Returns:
        POIBatchValidationResult with validation statistics
    """
    result = POIBatchValidationResult(total_processed=len(records))

    logger.info(
        f"Starting batch validation of {len(records)} records from {source_file}"
    )

    for i, record in enumerate(records):
        validated_poi = safe_validate_poi_record(record, f"{source_file}:record_{i+1}")

        if validated_poi is not None:
            result.valid_records.append(validated_poi)
        else:
            result.invalid_count += 1

    logger.info(
        f"Batch validation completed for {source_file}: "
        f"{len(result.valid_records)} valid, {result.invalid_count} invalid "
        f"({result.validation_rate:.1f}% success rate)"
    )

    return result
