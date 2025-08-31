import time, logging, hashlib
from django.http import JsonResponse
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_GET
from .services.region_stats import get_region_stats
from .helper import paginate_queryset, page_meta
from countries.validators import parse_stats_query

logger = logging.getLogger(__name__)


@require_GET
def stats(request):
    """
    API endpoint that returns aggregated region statistics
    (number of countries and total population per region),
    with optional filtering and pagination.
    Uses low-level caching so only the data is cached,
    execution_time_ms is fresh on every request.
    """

    start_time = time.time()

    try:
        page, per_page, name_filter = parse_stats_query(
            request, default_page=1, default_per_page=10
        )
    except ValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)

    # 🔑 Build a stable cache key based on the query parameters
    key_src = f"{page}:{per_page}:{name_filter or ''}"
    cache_key = "region_stats:" + hashlib.md5(key_src.encode("utf-8")).hexdigest()

    # Try cache first
    cached = cache.get(cache_key)
    if cached is None:
        # Query DB only if not in cache
        qs = get_region_stats(name_filter=name_filter)
        page_obj = paginate_queryset(qs, page, per_page)

        cached = {
            "regions": list(page_obj.object_list),
            "meta": page_meta(page_obj),
        }
        cache.set(cache_key, cached, timeout=60 * 5)  # cache for 5 min

    # Always recalc execution time fresh
    response = {
        "regions": cached["regions"],
        "meta": {
            **cached["meta"],
            "execution_time_ms": round((time.time() - start_time) * 1000, 3),
        },
    }

    return JsonResponse(response)