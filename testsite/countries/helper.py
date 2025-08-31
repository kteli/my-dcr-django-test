from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def paginate_queryset(queryset, page, per_page):
    """
    Robust pagination helper that never raises to the caller.
    Clamps out-of-range pages to the last page and non-integers to page 1.
    """
    paginator = Paginator(queryset, per_page)
    try:
        return paginator.page(page)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


def page_meta(page_obj):
    """
    Build a consistent metadata dict for a paginated page.
    """
    return {
        "total_regions": page_obj.paginator.count,
        "page": page_obj.number,
        "total_pages": page_obj.paginator.num_pages,
        "per_page": page_obj.paginator.per_page,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    }
