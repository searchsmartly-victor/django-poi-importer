"""
Models for the ingest app.
"""

from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import models


class PointOfInterest(models.Model):
    """
    Model representing a Point of Interest with location, category, and rating information.
    """

    SOURCE_CHOICES = [
        ("csv", "CSV"),
        ("json", "JSON"),
        ("xml", "XML"),
    ]

    id = models.AutoField(primary_key=True)
    external_id = models.CharField(max_length=128, db_index=True)
    source = models.CharField(max_length=16, db_index=True, choices=SOURCE_CHOICES)
    name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    category = models.CharField(max_length=64, db_index=True)
    ratings_raw = models.JSONField(null=True, blank=True)  # List of numbers or None
    avg_rating = models.DecimalField(
        max_digits=3, decimal_places=2, db_index=True
    )  # 0.00-5.00
    description = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["external_id", "source"], name="unique_external_id_source"
            ),
            models.CheckConstraint(
                condition=models.Q(avg_rating__gte=0) & models.Q(avg_rating__lte=5),
                name="avg_rating_range_check",
            ),
        ]
        indexes = [
            models.Index(fields=["category", "avg_rating"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.external_id})"

    def clean(self) -> None:
        """
        Custom validation for the model.
        """
        super().clean()

        # Validate avg_rating range
        if self.avg_rating is not None:
            if self.avg_rating < 0 or self.avg_rating > 5:
                raise ValidationError(
                    {"avg_rating": "Average rating must be between 0 and 5."}
                )

        # Validate ratings_raw if present
        if self.ratings_raw is not None:
            if not isinstance(self.ratings_raw, list):
                raise ValidationError(
                    {"ratings_raw": "Ratings raw must be a list or null."}
                )

            for rating in self.ratings_raw:
                if not isinstance(rating, (int, float)):
                    raise ValidationError(
                        {"ratings_raw": "All ratings must be numbers."}
                    )
                if rating < 0 or rating > 5:
                    raise ValidationError(
                        {"ratings_raw": "All ratings must be between 0 and 5."}
                    )

    def save(self, *args, **kwargs) -> None:
        """
        Custom save method with validation.
        """
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def has_ratings(self) -> bool:
        """
        Check if this POI has any ratings.
        """
        return self.ratings_raw is not None and len(self.ratings_raw) > 0

    @property
    def rating_count(self) -> int:
        """
        Get the count of ratings for this POI.
        """
        if self.ratings_raw is None:
            return 0
        return len(self.ratings_raw)

    def calculate_avg_rating(self) -> Optional[Decimal]:
        """
        Calculate the average rating from ratings_raw.
        """
        if not self.has_ratings:
            return None

        total = sum(self.ratings_raw)
        avg = total / len(self.ratings_raw)
        return Decimal(str(round(avg, 2)))
