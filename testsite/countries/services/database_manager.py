from typing import Dict, Iterable, List
import logging

from django.db import transaction

from countries.models import Country, Region

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Thin data-access layer to centralize bulk write logic and caches.
    Works with Django 2.2 and avoids per-row queries by using in-memory maps.
    """

    # ---------- destructive ops ----------
    @staticmethod
    def reset_database() -> None:
        """
        Deletes all Country and Region rows (order matters for FKs).
        """
        Country.objects.all().delete()
        Region.objects.all().delete()

    # ---------- caches ----------
    @staticmethod
    def preload_countries_by_name() -> Dict[str, Country]:
        """
        Preload all countries into a dict keyed by .name to avoid N+1 lookups.
        """
        qs = Country.objects.select_related("region").all()
        return {c.name: c for c in qs}

    @staticmethod
    def preload_regions_by_name() -> Dict[str, Region]:
        """
        Preload all regions into a dict keyed by .name to avoid N+1 lookups.
        """
        qs = Region.objects.all()
        return {r.name: r for r in qs}

    # ---------- region helpers ----------
    @staticmethod
    def get_or_create_region(
        name: str,
        cache: Dict[str, Region],
        dry_run: bool = False,
    ) -> Region:
        """
        Returns a Region from cache or creates it (and inserts into cache).
        In dry_run mode, creates an unsaved Region instance.
        """
        region = cache.get(name)
        if region is not None:
            return region

        region = Region(name=name)
        if not dry_run:
            region.save()
        cache[name] = region
        return region

    # ---------- bulk writes ----------
    @staticmethod
    def bulk_create_countries(
        objs: Iterable[Country],
        dry_run: bool = False,
        batch_size: int = 1000,
    ) -> int:
        objs = list(objs)
        if not objs:
            return 0
        if not dry_run:
            Country.objects.bulk_create(objs, batch_size=batch_size)
        logger.debug("bulk_create_countries: %s objects", len(objs))
        return len(objs)

    @staticmethod
    def bulk_update_countries(
        objs: Iterable[Country],
        dry_run: bool = False,
        batch_size: int = 1000,
    ) -> int:
        objs = list(objs)
        if not objs:
            return 0
        if not dry_run:
            Country.objects.bulk_update(
                objs,
                fields=[
                    "alpha2Code",
                    "alpha3Code",
                    "population",
                    "topLevelDomain",
                    "capital",
                    "region",
                ],
                batch_size=batch_size,
            )
        logger.debug("bulk_update_countries: %s objects", len(objs))
        return len(objs)

    # ---------- utility ----------
    @staticmethod
    def apply_changesets(
        to_create: List[Country],
        to_update: List[Country],
        dry_run: bool = False,
        batch_size: int = 1000,
        atomic: bool = True,
    ) -> int:
        """
        Applies both create and update batches. Optionally wraps in a transaction.
        Returns total number of affected rows.
        """
        def _apply():
            created = DatabaseManager.bulk_create_countries(
                to_create, dry_run=dry_run, batch_size=batch_size
            )
            updated = DatabaseManager.bulk_update_countries(
                to_update, dry_run=dry_run, batch_size=batch_size
            )
            return created + updated

        if atomic and not dry_run:
            with transaction.atomic():
                return _apply()
        return _apply()
