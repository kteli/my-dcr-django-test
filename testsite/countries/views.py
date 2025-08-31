from django.http import JsonResponse
from django.core.exceptions import ValidationError
import time, logging

from .services.region_stats import get_region_stats
from .helper import paginate_queryset, page_meta
from countries.validators import parse_stats_query

logger = logging.getLogger(__name__)

def stats(request):
    """
    API endpoint that returns aggregated region statistics
    (number of countries and total population per region),
    with optional filtering and pagination.
    """

    # Allow only GET requests
    if request.method != "GET":
        return JsonResponse({"error": "Only GET requests are allowed."}, status=400)

    start_time = time.time()

    # Parse query parameters (page, per_page, name_filter)
    try:
        page, per_page, name_filter = parse_stats_query(
            request, default_page=1, default_per_page=10
        )
    except ValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)

    # Run the stats query and apply pagination
    qs = get_region_stats(name_filter=name_filter)
    page_obj = paginate_queryset(qs, page, per_page)

    # Build the response payload
    response = {
        "regions": list(page_obj.object_list),
        "meta": {
            **page_meta(page_obj),
            "execution_time_ms": (time.time() - start_time) * 1000,
        },
    }

    return JsonResponse(response)