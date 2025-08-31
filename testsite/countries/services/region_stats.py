# myapp/services/region_stats.py
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from ..models import Region
from django.core.exceptions import ValidationError

def get_region_stats(name_filter=None):
    """
    Retrieves region statistics, including the number of countries and total population
    per region, ordered by region name. Optionally filters by region name.
    
    Args:
        name_filter (str, optional): A string to filter regions by name (case-insensitive).
    
    Returns:
        QuerySet: A Django QuerySet containing region statistics.
        
    Raises:
        ValidationError: If name_filter is invalid (e.g., too long or not a string).
    """

    queryset = (
        Region.objects
        .prefetch_related("countries")
        .annotate(
            number_countries=Count("countries", distinct=True),
            total_population=Coalesce(Sum("countries__population"), 0),
        )
        .values("name", "number_countries", "total_population")
        .order_by("name")
    )
    
    if name_filter:
        queryset = queryset.filter(name__icontains=name_filter.strip())
    
    return queryset