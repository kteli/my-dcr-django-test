from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from ..models import Region


def get_region_stats(name_filter=None):
    """
    Retrieves region statistics:
      - number of countries in the region
      - total population of the region

    Args:
        name_filter (str, optional): If provided, filters regions
                                     by case-insensitive containment.

    Returns:
        QuerySet of dicts with keys: name, number_countries, total_population
    """
    qs = (
        Region.objects
        .annotate(
            number_countries=Count("countries", distinct=True),
            total_population=Coalesce(Sum("countries__population"), 0),
        )
        .values("name", "number_countries", "total_population")
        .order_by("name")
    )

    if name_filter:
        qs = qs.filter(name__icontains=name_filter.strip())

    return qs
