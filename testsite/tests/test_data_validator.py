import json
from django.test import TestCase

from countries.services.data_validator import DataValidator, CountryDataValidationError

class DataValidatorTests(TestCase):
    def setUp(self):
        self.valid_row = {
            "name": "Wonderland",
            "region": "Fiction",
            "alpha2Code": "wl",
            "alpha3Code": "wnl",
            "population": 123456,
            "topLevelDomain": [".wl"],
            "capital": "Heart City",
        }

    def test_valid_row_passes_and_normalizes(self):
        cleaned = DataValidator.validate_row(self.valid_row.copy(), index=0)

        # required keys exist
        for key in (
            "name",
            "region",
            "alpha2Code",
            "alpha3Code",
            "population",
            "topLevelDomain",
            "capital",
        ):
            self.assertIn(key, cleaned)

        # uppercasing applied
        self.assertEqual(cleaned["alpha2Code"], "WL")
        self.assertEqual(cleaned["alpha3Code"], "WNL")

        # TLD normalized to compact JSON string
        self.assertIsInstance(cleaned["topLevelDomain"], str)
        self.assertEqual(json.loads(cleaned["topLevelDomain"]), [".wl"])

        # capital kept
        self.assertEqual(cleaned["capital"], "Heart City")

    def test_missing_required_keys_raises(self):
        bad = self.valid_row.copy()
        bad.pop("alpha2Code")
        with self.assertRaises(CountryDataValidationError):
            DataValidator.validate_row(bad, index=1)

    def test_invalid_tld_string_rejected(self):
        bad = self.valid_row.copy()
        bad["topLevelDomain"] = "not-a-json-array"
        with self.assertRaises(CountryDataValidationError):
            DataValidator.validate_row(bad, index=2)

    def test_invalid_tld_item_filtered_but_not_fatal(self):
        row = self.valid_row.copy()
        row["topLevelDomain"] = [".ok", " ", 123, "bad", ".also-ok"]
        cleaned = DataValidator.validate_row(row, index=3)
        self.assertEqual(json.loads(cleaned["topLevelDomain"]), [".ok", ".also-ok"])

    def test_empty_capital_becomes_none(self):
        row = self.valid_row.copy()
        row["capital"] = ""
        cleaned = DataValidator.validate_row(row, index=4)
        self.assertIsNone(cleaned["capital"])

    def test_population_must_be_int(self):
        row = self.valid_row.copy()
        row["population"] = -1  # validator min=0
        with self.assertRaises(CountryDataValidationError):
            DataValidator.validate_row(row, index=5)

    def test_alpha_codes_length_enforced(self):
        row = self.valid_row.copy()
        row["alpha2Code"] = "WLL"  # too long
        with self.assertRaises(CountryDataValidationError):
            DataValidator.validate_row(row, index=6)

        row = self.valid_row.copy()
        row["alpha3Code"] = "WN"  # too short
        with self.assertRaises(CountryDataValidationError):
            DataValidator.validate_row(row, index=7)
