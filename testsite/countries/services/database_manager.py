from typing import List, Dict, Tuple
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from countries.models import Country, Region
from countries.services.data_validator import CountryDataValidationError
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Service for managing database operations for Country and Region models."""

    @staticmethod
    @transaction.atomic
    def reset_database() -> None:
        """Clear the Country and Region tables.

        Raises:
            IntegrityError: If the reset operation fails.
        """
        try:
            Country.objects.all().delete()
            Region.objects.all().delete()
            logger.info("Database reset successful")
        except Exception as e:
            logger.error("Reset database failed", exc_info=True)
            raise

    @staticmethod
    def get_or_create_region(name: str, existing_regions: Dict[str, Region], dry_run: bool = False) -> Region:
        """Get or create a Region instance.

        Args:
            name: Region name.
            existing_regions: Cache of existing regions.
            dry_run: If True, simulate region creation.

        Returns:
            Region instance.

        Raises:
            CountryDataValidationError: If region validation or saving fails.
        """
        if name in existing_regions:
            return existing_regions[name]

        region = Region(name=name)
        try:
            region.full_clean()
            if not dry_run:
                region.save()
            existing_regions[name] = region
            return region
        except (ValidationError, IntegrityError) as e:
            raise CountryDataValidationError(f"Region '{name}' validation failed: {e}")

    @staticmethod
    def get_existing_countries() -> set:
        """Fetch existing country names from the database.

        Returns:
            Set of existing country names.
        """
        return set(Country.objects.values_list("name", flat=True).iterator())

    @staticmethod
    def get_existing_regions() -> Dict[str, Region]:
        """Fetch existing regions from the database.

        Returns:
            Dictionary mapping region names to Region objects.
        """
        return {r.name: r for r in Region.objects.all().only("name", "id")}

    @staticmethod
    def bulk_create_countries(countries: List[Country], dry_run: bool = False) -> int:
        """Create multiple Country objects in bulk.

        Args:
            countries: List of Country objects to create.
            dry_run: If True, simulate creation.

        Returns:
            Number of countries created (or would be created in dry-run).
        """
        if not countries:
            return 0
        if dry_run:
            logger.info(f"[Dry Run] Would create {len(countries)} countries")
            return len(countries)
        Country.objects.bulk_create(countries)
        logger.info(f"Created {len(countries)} countries")
        return len(countries)

    @staticmethod
    def bulk_update_countries(countries: List[Country], dry_run: bool = False) -> int:
        """Update multiple Country objects in bulk.

        Args:
            countries: List of Country objects to update.
            dry_run: If True, simulate update.

        Returns:
            Number of countries updated (or would be updated in dry-run).
        """
        if not countries:
            return 0
        if dry_run:
            logger.info(f"[Dry Run] Would update {len(countries)} countries")
            return len(countries)
        Country.objects.bulk_update(
            countries,
            ["alpha2Code", "alpha3Code", "population", "topLevelDomain", "capital", "region"],
        )
        logger.info(f"Updated {len(countries)} countries")
        return len(countries)