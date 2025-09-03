"""
DRF views for the ingest app.
"""


from django.db.models import QuerySet
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .models import PointOfInterest
from .serializers import PointOfInterestSerializer


class PointOfInterestViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for PointOfInterest model providing list and retrieve operations.

    Supports filtering by:
    - id: Exact match by internal ID (?id=123)
    - external_id: Exact match by external ID (?external_id=poi_001)
    - category: Filter by category (?category=restaurant)

    Results are ordered by name with pagination of 25 records per page.
    """

    serializer_class = PointOfInterestSerializer
    pagination_class = None  # Will use default pagination from settings

    # Filtering and search
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["name", "category", "avg_rating", "id"]
    ordering = ["name"]  # Default ordering by name

    def get_queryset(self) -> QuerySet[PointOfInterest]:
        """
        Get the queryset with optimizations for future relations.
        """
        queryset = PointOfInterest.objects.all()

        # Prepare for future relations with select_related/prefetch_related
        # Currently no relations, but hooks are prepared
        # queryset = queryset.select_related('category_relation')  # Future
        # queryset = queryset.prefetch_related('ratings_relation')  # Future

        # Apply filtering
        queryset = self._apply_filters(queryset)

        return queryset

    def _apply_filters(
        self, queryset: QuerySet[PointOfInterest]
    ) -> QuerySet[PointOfInterest]:
        """
        Apply custom filters based on query parameters.
        """
        request = self.request

        # Filter by internal ID (exact match)
        id_param = request.query_params.get("id")
        if id_param:
            try:
                queryset = queryset.filter(id=int(id_param))
            except (ValueError, TypeError):
                # Invalid ID format, return empty queryset
                queryset = queryset.none()

        # Filter by external_id (exact match)
        external_id_param = request.query_params.get("external_id")
        if external_id_param:
            queryset = queryset.filter(external_id=external_id_param)

        # Filter by category
        category_param = request.query_params.get("category")
        if category_param:
            queryset = queryset.filter(category=category_param)

        # Filter by source
        source_param = request.query_params.get("source")
        if source_param and source_param in ["csv", "json", "xml"]:
            queryset = queryset.filter(source=source_param)

        # Filter by rating range
        min_rating = request.query_params.get("min_rating")
        if min_rating:
            try:
                queryset = queryset.filter(avg_rating__gte=float(min_rating))
            except (ValueError, TypeError):
                pass  # Ignore invalid rating values

        max_rating = request.query_params.get("max_rating")
        if max_rating:
            try:
                queryset = queryset.filter(avg_rating__lte=float(max_rating))
            except (ValueError, TypeError):
                pass  # Ignore invalid rating values

        return queryset

    def list(self, request: Request, *args, **kwargs) -> Response:
        """
        List POIs with filtering and pagination.
        """
        # Add custom headers for API documentation
        response = super().list(request, *args, **kwargs)

        # Add filter information to response headers
        if hasattr(response, "data") and isinstance(response.data, dict):
            # Add metadata about available filters
            if "results" in response.data:
                response.data["filters"] = {
                    "available_filters": [
                        "id - exact match by internal ID",
                        "external_id - exact match by external ID",
                        "category - filter by category",
                        "source - filter by source (csv/json/xml)",
                        "min_rating - minimum average rating",
                        "max_rating - maximum average rating",
                    ],
                    "ordering": "Use ?ordering=field_name (name, category, avg_rating, id)",
                }

        return response

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """
        Retrieve a specific POI by ID.
        """
        return super().retrieve(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def categories(self, request: Request) -> Response:
        """
        Get list of all available categories.
        """
        categories = (
            PointOfInterest.objects.values_list("category", flat=True)
            .distinct()
            .order_by("category")
        )

        return Response({"categories": list(categories), "count": len(categories)})

    @action(detail=False, methods=["get"])
    def sources(self, request: Request) -> Response:
        """
        Get list of all available data sources.
        """
        sources = (
            PointOfInterest.objects.values_list("source", flat=True)
            .distinct()
            .order_by("source")
        )

        return Response({"sources": list(sources), "count": len(sources)})

    @action(detail=False, methods=["get"])
    def stats(self, request: Request) -> Response:
        """
        Get statistics about the POI dataset.
        """
        from django.db.models import Count, Avg, Min, Max

        queryset = self.get_queryset()

        stats = queryset.aggregate(
            total_pois=Count("id"),
            avg_rating=Avg("avg_rating"),
            min_rating=Min("avg_rating"),
            max_rating=Max("avg_rating"),
        )

        # Category breakdown
        category_stats = (
            queryset.values("category").annotate(count=Count("id")).order_by("-count")
        )

        # Source breakdown
        source_stats = (
            queryset.values("source").annotate(count=Count("id")).order_by("-count")
        )

        return Response(
            {
                "total_statistics": stats,
                "by_category": list(category_stats),
                "by_source": list(source_stats),
            }
        )
