"""
Admin configuration for the ingest app.
"""

from typing import Any
from decimal import Decimal
import logging

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import PointOfInterest

logger = logging.getLogger(__name__)


@admin.register(PointOfInterest)
class PointOfInterestAdmin(admin.ModelAdmin):
    """
    Admin interface for PointOfInterest model.

    Search functionality:
    - Internal ID: Use exact ID number (e.g., "123")
    - External ID: Use exact external ID (e.g., "poi_001")
    - Name: Use partial text search (e.g., "restaurant")

    Filters available:
    - Category: Filter by POI category
    - Source: Filter by data source (CSV, JSON, XML)
    """

    list_display = (
        "id",
        "name",
        "external_id",
        "category",
        "avg_rating",
        "rating_count_display",
    )
    search_fields = ("=id", "=external_id", "name")
    list_filter = ("category", "source")
    ordering = ("name",)
    list_per_page = 50
    readonly_fields = ("avg_rating",)

    # Custom search help text
    search_help_text = (
        "Search by: Internal ID (exact match), External ID (exact match), "
        "or POI Name (partial match). "
        "Examples: '123' for ID, 'poi_001' for External ID, 'restaurant' for name."
    )

    # Additional search configuration
    preserve_filters = True  # Preserve filters when navigating
    show_full_result_count = True  # Show exact count even for large datasets

    # Additional admin configurations for better UX
    list_display_links = ("id", "name")

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "external_id", "source", "category")},
        ),
        ("Location", {"fields": ("latitude", "longitude")}),
        (
            "Ratings",
            {
                "fields": ("ratings_raw", "avg_rating"),
                "description": "Average rating is automatically calculated from ratings_raw",
            },
        ),
        (
            "Additional Information",
            {"fields": ("description",), "classes": ("collapse",)},
        ),
    )

    actions = ["recompute_average_ratings"]

    def recompute_average_ratings(
        self, request: HttpRequest, queryset: QuerySet[PointOfInterest]
    ) -> None:
        """
        Admin action to recompute average ratings from ratings_raw.
        """
        updated_count = 0
        error_count = 0

        for poi in queryset:
            try:
                if poi.ratings_raw is not None and len(poi.ratings_raw) > 0:
                    # Calculate new average
                    new_avg = poi.calculate_avg_rating()
                    if new_avg is not None:
                        # Update only if there's a change
                        if poi.avg_rating != new_avg:
                            poi.avg_rating = new_avg
                            poi.save(update_fields=["avg_rating"])
                            updated_count += 1
                            logger.info(
                                f"Updated avg_rating for POI {poi.id} ({poi.name}) "
                                f"from {poi.avg_rating} to {new_avg}"
                            )
                else:
                    # No ratings available, set to 0
                    if poi.avg_rating != Decimal("0.00"):
                        poi.avg_rating = Decimal("0.00")
                        poi.save(update_fields=["avg_rating"])
                        updated_count += 1
                        logger.info(
                            f"Reset avg_rating for POI {poi.id} ({poi.name}) to 0.00 (no ratings)"
                        )
            except Exception as e:
                error_count += 1
                logger.error(
                    f"Error recomputing avg_rating for POI {poi.id} ({poi.name}): {e}"
                )

        # Display success/error message
        if updated_count > 0:
            self.message_user(
                request,
                f"Successfully recomputed average ratings for {updated_count} Point(s) of Interest.",
            )

        if error_count > 0:
            self.message_user(
                request,
                f"Encountered errors while processing {error_count} Point(s) of Interest. "
                f"Check logs for details.",
                level="ERROR",
            )

        if updated_count == 0 and error_count == 0:
            self.message_user(request, "No average ratings needed to be updated.")

    recompute_average_ratings.short_description = "Recompute average ratings"

    def rating_count_display(self, obj: PointOfInterest) -> str:
        """
        Display the number of ratings for this POI in the admin list.
        """
        count = obj.rating_count
        if count == 0:
            return "No ratings"
        elif count == 1:
            return "1 rating"
        else:
            return f"{count} ratings"

    rating_count_display.short_description = "Rating Count"
    rating_count_display.admin_order_field = "ratings_raw"

    def save_model(
        self, request: HttpRequest, obj: PointOfInterest, form: Any, change: bool
    ) -> None:
        """
        Custom save logic to automatically compute avg_rating when saving.
        """
        # Calculate avg_rating from ratings_raw if available
        if obj.ratings_raw is not None and len(obj.ratings_raw) > 0:
            calculated_avg = obj.calculate_avg_rating()
            if calculated_avg is not None:
                obj.avg_rating = calculated_avg
        else:
            # No ratings, set to 0
            obj.avg_rating = Decimal("0.00")

        super().save_model(request, obj, form, change)

        if change:
            logger.info(f"Updated POI {obj.id} ({obj.name}) via admin interface")
        else:
            logger.info(f"Created new POI {obj.id} ({obj.name}) via admin interface")
