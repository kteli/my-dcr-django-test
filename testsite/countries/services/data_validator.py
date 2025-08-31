from typing import Dict, Any
import json, logging
from countries.validators import CountryRowForm

logger = logging.getLogger(__name__)

class CountryDataValidationError(Exception):
    """Raised when a country data row fails validation."""
    pass


class DataValidator:
    """
    Validates and normalizes raw country rows coming from the remote JSON.
    Ensures types and formats are consistent with models and downstream code.
    """

    REQUIRED_KEYS = {"name", "region", "alpha2Code", "alpha3Code", "population"}

    @staticmethod
    def validate_row(row: Dict[str, Any], index: int) -> Dict[str, Any]:
        """
        Validate a single row and return cleaned data.

        - Ensures required keys are present.
        - Uses CountryRowForm for field-level validation & normalization.
        - Normalizes topLevelDomain to a compact JSON string.
        - Normalizes empty capital -> None.

        Returns a dict with keys:
          name, region, alpha2Code, alpha3Code, population,
          topLevelDomain (JSON string), capital (str or None)
        """
        missing = DataValidator.REQUIRED_KEYS - set(row.keys())
        if missing:
            raise CountryDataValidationError(
                f"Row {index} missing required keys: {sorted(missing)}"
            )

        # Accept absent topLevelDomain/capital gracefully
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
            # Log the form errors for observability and raise a concise exception
            logger.debug("Row %s form errors: %s", index, form.errors.as_json())
            raise CountryDataValidationError(
                f"Row {index} invalid: {form.errors.as_json()}"
            )

        cleaned = form.cleaned_data

        # Ensure final shapes/types are exactly what the model expects
        # - topLevelDomain must be a JSON string (already ensured by clean_topLevelDomain)
        # - capital should be None or a non-empty string (clean_capital handles this)
        return {
            "name": cleaned["name"],
            "region": cleaned["region"],
            "alpha2Code": cleaned["alpha2Code"],
            "alpha3Code": cleaned["alpha3Code"],
            "population": cleaned["population"],
            "topLevelDomain": cleaned["topLevelDomain"],  # JSON string
            "capital": cleaned.get("capital"),            # None or str
        }