from typing import List, Dict, Any, Tuple
import contextlib
import logging
from requests.exceptions import RequestException
from tqdm import tqdm
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


from countries.services.api_client import APIClient
from countries.services.data_validator import DataValidator, CountryDataValidationError
from countries.services.database_manager import DatabaseManager
from countries.models import Country

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """Loads country data from a remote JSON file with all-or-nothing consistency.

    Options:
        --batch-size: Number of records to process per batch (default: 1000).
        --dry-run: Simulate the import without making database changes.
        --reset: Clear the database before importing.
        --save-response: Save API response to api_response.json for debugging.
    """
    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Batch size for database operations (must be positive)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate import without database changes",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear database before import",
        )
        parser.add_argument(
            "--save-response",
            action="store_true",
            help="Save API response to api_response.json",
        )

    def process_records(self, data: List[Dict[str, Any]], batch_size: int, dry_run: bool, reset: bool) -> Tuple[int, int, int]:
        """Process country data records and update the database.

        Args:
            data: List of country data dictionaries.
            batch_size: Maximum batch size for database operations.
            dry_run: If True, simulate operations.
            reset: If True, clear the database before processing.

        Returns:
            Tuple of (created, updated, skipped) counts.
        """
        created_count, updated_count, skipped_count = 0, 0, 0

        if reset:
            self.stdout.write(self.style.WARNING("Resetting database..."))
            if not dry_run:
                DatabaseManager.reset_database()
            else:
                self.stdout.write("[Dry Run] Would reset database")

        existing_countries = DatabaseManager.get_existing_countries()
        existing_regions = DatabaseManager.get_existing_regions()
        to_create, to_update = [], []

        for idx, row in tqdm(enumerate(data), total=len(data), desc="Processing rows"):
            try:
                validated_row = DataValidator.validate_row(row, idx)
            except CountryDataValidationError as e:
                logger.warning(str(e))
                continue

            region = DatabaseManager.get_or_create_region(validated_row["region"], existing_regions, dry_run)

            country_data = {
                "name": validated_row["name"],
                "alpha2Code": validated_row["alpha2Code"],
                "alpha3Code": validated_row["alpha3Code"],
                "population": validated_row["population"],
                "topLevelDomain": validated_row["topLevelDomain"],
                "capital": validated_row["capital"],
                "region": region,
            }

            country = Country(**country_data)
            try:
                country.full_clean()
            except ValidationError as e:
                logger.warning(f"Validation failed for {country.name}: {e}")
                continue

            if country.name not in existing_countries:
                to_create.append(country)
                created_count += 1
                self.stdout.write(f"🟢 Create: {country.name}")
            else:
                existing = Country.objects.get(name=country.name)
                if any(getattr(existing, k) != v for k, v in country_data.items() if k != "region"):
                    for key, val in country_data.items():
                        setattr(existing, key, val)
                    to_update.append(existing)
                    updated_count += 1
                    self.stdout.write(f"🟡 Update: {country.name}")
                else:
                    skipped_count += 1
                    self.stdout.write(f"⚪ Skipped: {country.name}")

            if len(to_create) >= batch_size or len(to_update) >= batch_size:
                created_count += DatabaseManager.bulk_create_countries(to_create, dry_run)
                updated_count += DatabaseManager.bulk_update_countries(to_update, dry_run)
                to_create.clear()
                to_update.clear()

        # Flush remaining records
        created_count += DatabaseManager.bulk_create_countries(to_create, dry_run)
        updated_count += DatabaseManager.bulk_update_countries(to_update, dry_run)

        return created_count, updated_count, skipped_count

    def handle(self, *args, **options):
        """Execute the command to import country data.

        Args:
            options: Command-line options (batch_size, dry_run, reset, save_response).

        Raises:
            CommandError: If an error occurs during execution.
        """
        batch_size = options["batch_size"]
        if batch_size <= 0:
            raise CommandError("Batch size must be a positive integer")

        try:
            logger.info(f"Starting import with batch_size={batch_size}, dry_run={options['dry_run']}, reset={options['reset']}")
            api_client = APIClient()
            data = api_client.fetch_data(save_response=options["save_response"])

            with transaction.atomic() if not options["dry_run"] else contextlib.suppress():
                created, updated, skipped = self.process_records(
                    data,
                    batch_size=batch_size,
                    dry_run=options["dry_run"],
                    reset=options["reset"],
                )
                if options["dry_run"]:
                    self.stdout.write("[Dry Run] No changes committed")
                    return

            self.stdout.write(
                self.style.SUCCESS(
                    f"🎉 Import completed successfully. Summary: Created {created}, Updated {updated}, Skipped {skipped}"
                )
            )
        except (CountryDataValidationError, ValueError, RequestException) as e:
            self.stderr.write(self.style.ERROR(str(e)))
            raise CommandError(str(e))
        except Exception as e:
            logger.error("Unexpected error during import", exc_info=True)
            self.stderr.write(self.style.ERROR(f"Unexpected error: {e}"))
            raise