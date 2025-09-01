import json
from unittest import mock

from django.test import TestCase, override_settings
from django.core.management import call_command
from django.core.cache import cache

from countries.models import Country, Region


# Use a local in-memory cache backend during these tests
TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-countries-cache",
    }
}


@override_settings(CACHES=TEST_CACHES)
class UpdateCountryListingCommandTests(TestCase):
    def setUp(self):
        cache.clear()

        # Basic sample payload from the remote JSON structure
        self.sample_data = [
            {
                "name": "Testland",
                "alpha2Code": "TL",
                "alpha3Code": "TST",
                "population": 12345,
                "region": "Europe",
                "topLevelDomain": [".tl"],
                "capital": "Exam City",
            },
            {
                "name": "Examplestan",
                "alpha2Code": "EX",
                "alpha3Code": "EXP",
                "population": 67890,
                "region": "Asia",
                "topLevelDomain": [".ex", ".example"],
                "capital": "Sampleville",
            },
        ]

    def _patch_api(self):
        """
        Patch the APIClient inside the command module so the command
        uses our sample payload instead of making a real HTTP request.
        """
        patcher = mock.patch(
            "countries.management.commands.update_country_listing.APIClient",
            autospec=True,
        )
        mocked_api_cls = patcher.start()
        self.addCleanup(patcher.stop)

        mocked_api = mocked_api_cls.return_value
        mocked_api.fetch_data.return_value = self.sample_data
        return mocked_api

    def test_import_creates_regions_and_countries(self):
        mocked_api = self._patch_api()

        call_command("update_country_listing", "--no-progress")

        # API was called
        mocked_api.fetch_data.assert_called_once()

        # Regions created
        self.assertEqual(Region.objects.count(), 2)
        self.assertTrue(Region.objects.filter(name="Europe").exists())
        self.assertTrue(Region.objects.filter(name="Asia").exists())

        # Countries created
        self.assertEqual(Country.objects.count(), 2)

        t = Country.objects.get(name="Testland")
        self.assertEqual(t.alpha2Code, "TL")
        self.assertEqual(t.alpha3Code, "TST")
        self.assertEqual(t.population, 12345)
        self.assertEqual(t.region.name, "Europe")
        self.assertEqual(json.loads(t.topLevelDomain), [".tl"])
        self.assertEqual(t.capital, "Exam City")

        e = Country.objects.get(name="Examplestan")
        self.assertEqual(json.loads(e.topLevelDomain), [".ex", ".example"])

    def test_import_updates_existing_country(self):
        # Seed DB with existing country but stale population & fields
        europe = Region.objects.create(name="Europe")
        Country.objects.create(
            name="Testland",
            alpha2Code="TL",
            alpha3Code="TST",
            population=1,  # will be updated to 12345
            region=europe,
            topLevelDomain="[]",
            capital=None,
        )

        mocked_api = self._patch_api()

        call_command("update_country_listing", "--no-progress")

        # Should still be 2 countries total (1 updated + 1 created)
        self.assertEqual(Country.objects.count(), 2)

        t = Country.objects.get(name="Testland")
        self.assertEqual(t.population, 12345)
        self.assertEqual(json.loads(t.topLevelDomain), [".tl"])
        self.assertEqual(t.capital, "Exam City")
        self.assertEqual(t.region.name, "Europe")  # unchanged

    def test_dry_run_makes_no_changes_and_does_not_clear_cache(self):
        mocked_api = self._patch_api()

        with mock.patch("countries.management.commands.update_country_listing.cache.clear") as m_clear:
            call_command("update_country_listing", "--dry-run", "--no-progress")

            # No DB changes
            self.assertEqual(Region.objects.count(), 0)
            self.assertEqual(Country.objects.count(), 0)

            # Cache not cleared on dry-run
            m_clear.assert_not_called()

    def test_reset_flag_clears_then_reimports(self):
        # Seed some unrelated data to ensure it gets wiped
        r = Region.objects.create(name="Oceania")
        Country.objects.create(
            name="Oldland",
            alpha2Code="OL",
            alpha3Code="OLD",
            population=999,
            region=r,
            topLevelDomain='[".ol"]',
            capital="Old City",
        )

        mocked_api = self._patch_api()

        call_command("update_country_listing", "--reset", "--no-progress")

        # Old data removed, new imported
        self.assertFalse(Country.objects.filter(name="Oldland").exists())
        self.assertTrue(Country.objects.filter(name="Testland").exists())
        self.assertTrue(Country.objects.filter(name="Examplestan").exists())

    def test_cache_cleared_after_successful_import(self):
        mocked_api = self._patch_api()

        with mock.patch("countries.management.commands.update_country_listing.cache.clear") as m_clear:
            call_command("update_country_listing", "--no-progress")
            m_clear.assert_called_once()
