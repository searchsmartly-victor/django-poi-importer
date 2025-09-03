"""
DRF serializers for the ingest app.
"""

from rest_framework import serializers

from .models import PointOfInterest


class PointOfInterestSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for PointOfInterest model.

    Includes the same fields as the admin list display for consistency.
    """

    class Meta:
        model = PointOfInterest
        fields = [
            "id",
            "external_id",
            "source",
            "name",
            "latitude",
            "longitude",
            "category",
            "avg_rating",
            "ratings_raw",
            "description",
        ]
        read_only_fields = fields  # All fields are read-only

    def to_representation(self, instance: PointOfInterest) -> dict:
        """
        Customize the serialized representation.
        """
        data = super().to_representation(instance)

        # Add computed fields for better API experience
        data["rating_count"] = instance.rating_count
        data["has_ratings"] = instance.has_ratings

        # Format coordinates as a nested object for convenience
        data["coordinates"] = {
            "latitude": instance.latitude,
            "longitude": instance.longitude,
        }

        return data
