from typing import List, Dict, Any, Tuple
import contextlib,logging
from django.core.cache import cache

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.core.exceptions import ValidationError

from tqdm import tqdm

from countries.services.api_client import APIClient
from countries.services.data_validator import DataValidator, CountryDataValidationError
from countries.services.database_manager import DatabaseManager
from countries.models import Country

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Import/refresh country data from the remote JSON endpoint.

    Examples:
      python manage.py update_country_listing
      python manage.py update_country_listing --dry-run
      python manage.py update_country_listing --reset
      python manage.py update_country_listing --batch-size=500 --no-progress
      python manage.py update_country_listing --save-response
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Batch size for bulk_create/bulk_update (must be positive)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the import without writing to the database",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all existing data before importing",
        )
        parser.add_argument(
            "--save-response",
            action="store_true",
            help="Save fetched API JSON to api_response.json for debugging",
        )
        parser.add_argument(
            "--no-progress",
            action="store_true",
            help="Disable progress bar output (CI-friendly)",
        )

    # -----------------------------
    # core processing
    # -----------------------------
    def process_records(
        self,
        data: List[Dict[str, Any]],
        batch_size: int,
        dry_run: bool,
        reset: bool,
        show_progress: bool,
    ) -> Tuple[int, int, int]:
        """
        Validate rows and compute create/update changesets.
        Applies writes in chunks to avoid large memory spikes.

        Returns: (created_count, updated_count, skipped_count)
        """
        created_count = updated_count = skipped_count = 0

        # Optional destructive reset
        if reset:
            self.stdout.write(self.style.WARNING("Resetting database..."))
            if not dry_run:
                DatabaseManager.reset_database()
            else:
                self.stdout.write("[Dry Run] Would reset database")

        # Preload caches to avoid N+1
        regions_by_name = DatabaseManager.preload_regions_by_name()
        countries_by_name = DatabaseManager.preload_countries_by_name()

        to_create: List[Country] = []
        to_update: List[Country] = []

        iterable = enumerate(data)
        if not show_progress:
            iterator = iterable
        else:
            iterator = tqdm(iterable, total=len(data), desc="Processing rows")

        for idx, row in iterator:
            # Validate/normalize a single row
            try:
                cleaned = DataValidator.validate_row(row, idx)
            except CountryDataValidationError as e:
                logger.warning(str(e))
                skipped_count += 1
                continue

            # Region instance from cache (created if needed)
            region = DatabaseManager.get_or_create_region(
                cleaned["region"], regions_by_name, dry_run=dry_run
            )

            # Prepare dict for model comparison
            desired = {
                "name": cleaned["name"],
                "alpha2Code": cleaned["alpha2Code"],
                "alpha3Code": cleaned["alpha3Code"],
                "population": cleaned["population"],
                "topLevelDomain": cleaned["topLevelDomain"],  # JSON string
                "capital": cleaned.get("capital"),
                "region": region,
            }

            existing = countries_by_name.get(desired["name"])

            if existing is None:
                # New country
                country = Country(**desired)
                # If you rely solely on form validation, you can skip full_clean()
                try:
                    country.full_clean()
                except ValidationError as e:
                    logger.warning("Validation failed for %s: %s", desired["name"], e)
                    skipped_count += 1
                    continue
                to_create.append(country)
                countries_by_name[desired["name"]] = country  # keep cache consistent
                created_count += 1
                # Flush in batches
                if len(to_create) >= batch_size:
                    created_count += DatabaseManager.bulk_create_countries(
                        to_create, dry_run=dry_run, batch_size=batch_size
                    ) - len(to_create)
                    to_create.clear()
            else:
                # Compare and update in-memory; mark for bulk_update if changed
                changed = False
                for field in (
                    "alpha2Code",
                    "alpha3Code",
                    "population",
                    "topLevelDomain",
                    "capital",
                    "region",
                ):
                    new_val = desired[field]
                    if getattr(existing, field) != new_val:
                        setattr(existing, field, new_val)
                        changed = True
                if changed:
                    to_update.append(existing)
                    updated_count += 1
                    if len(to_update) >= batch_size:
                        updated_count += DatabaseManager.bulk_update_countries(
                            to_update, dry_run=dry_run, batch_size=batch_size
                        ) - len(to_update)
                        to_update.clear()
                else:
                    skipped_count += 1

        # Flush tail batches
        if to_create:
            created_count += DatabaseManager.bulk_create_countries(
                to_create, dry_run=dry_run, batch_size=batch_size
            ) - len(to_create)
            to_create.clear()

        if to_update:
            updated_count += DatabaseManager.bulk_update_countries(
                to_update, dry_run=dry_run, batch_size=batch_size
            ) - len(to_update)
            to_update.clear()

        return created_count, updated_count, skipped_count

    # -----------------------------
    # command entrypoint
    # -----------------------------
    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        reset = options["reset"]
        save_response = options["save_response"]
        show_progress = not options["no_progress"]

        if batch_size <= 0:
            raise CommandError("Batch size must be a positive integer")

        logger.info(
            "Starting import: batch_size=%s dry_run=%s reset=%s",
            batch_size, dry_run, reset
        )

        # Fetch
        api = APIClient()
        data = api.fetch_data(save_response=save_response)

        # Apply in a single transaction unless dry-run
        ctx = transaction.atomic() if not dry_run else contextlib.suppress()
        try:
            with ctx:
                created, updated, skipped = self.process_records(
                    data,
                    batch_size=batch_size,
                    dry_run=dry_run,
                    reset=reset,
                    show_progress=show_progress,
                )
                if dry_run:
                    self.stdout.write(self.style.WARNING("[Dry Run] No changes committed"))
                    return
            # ✅ Clear cache after successful import (not dry-run)
            cache.clear()
            logger.info("Cache cleared after country import")

            self.stdout.write(
                self.style.SUCCESS(
                    f"🎉 Import completed. Created: {created}, Updated: {updated}, Skipped: {skipped}"
                )
            )
        except (CountryDataValidationError, ValueError) as e:
            self.stderr.write(self.style.ERROR(str(e)))
            raise CommandError(str(e))
        except Exception as e:
            logger.exception("Unexpected error during import")
            self.stderr.write(self.style.ERROR(f"Unexpected error: {e}"))
            raise CommandError(str(e))
