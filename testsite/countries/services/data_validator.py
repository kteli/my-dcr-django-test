from typing import Dict, Any
import logging, json

from countries.validators import CountryRowForm

logger = logging.getLogger(__name__)

class CountryDataValidationError(Exception):
    """Custom exception for country data validation errors."""
    pass

class DataValidator:
    """Service for validating and transforming country data rows."""

    @staticmethod
    def validate_row(row: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Validate and cast a single row of country data.

        Args:
            row: Dictionary containing raw country data.
            index: Row index for error reporting.

        Returns:
            Validated and cleaned data dictionary.

        Raises:
            CountryDataValidationError: If the row fails validation.
        """
        required_keys = {"name", "region", "alpha2Code", "alpha3Code", "population", "capital"}
        if not all(key in row for key in required_keys):
            raise CountryDataValidationError(f"Row {index} missing required keys: {required_keys - set(row)}")

        form_data = {
            "name": row.get("name", ""),
            "region": row.get("region", ""),
            "alpha2Code": row.get("alpha2Code", ""),
            "alpha3Code": row.get("alpha3Code", ""),
            "population": row.get("population"),
            "topLevelDomain": json.dumps(row.get("topLevelDomain", [])),
            "capital": row.get("capital", ""),
        }

        form = CountryRowForm(data=form_data)
        if not form.is_valid():
            raise CountryDataValidationError(f"Row {index} invalid: {form.errors.as_json()}")

        return form.cleaned_data