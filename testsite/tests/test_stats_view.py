from django.test import TestCase, Client
from django.core.cache import cache
from countries.models import Region, Country

class StatsViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Regions
        africa = Region.objects.create(name="Africa")
        europe = Region.objects.create(name="Europe")

        # Countries (keep numbers small but distinct)
        Country.objects.create(
            name="Nigeria", alpha2Code="NG", alpha3Code="NGA",
            population=200_000_000, region=africa,
            topLevelDomain='[".ng"]', capital="Abuja",
        )
        Country.objects.create(
            name="Kenya", alpha2Code="KE", alpha3Code="KEN",
            population=50_000_000, region=africa,
            topLevelDomain='[".ke"]', capital="Nairobi",
        )
        Country.objects.create(
            name="France", alpha2Code="FR", alpha3Code="FRA",
            population=67_000_000, region=europe,
            topLevelDomain='[".fr"]', capital="Paris",
        )

    def setUp(self):
        self.client = Client()
        cache.clear()  # ensure caching doesn’t affect expectations

    def test_stats_basic_shape(self):
        resp = self.client.get("/countries/stats/")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()

        # top-level keys
        self.assertIn("regions", payload)
        self.assertIn("meta", payload)

        # meta presence & pagination meta keys
        meta = payload["meta"]
        for key in ("total_regions", "page", "total_pages", "per_page", "has_next", "has_previous"):
            self.assertIn(key, meta)

        # regions list and dict shape
        regions = payload["regions"]
        self.assertIsInstance(regions, list)
        self.assertGreaterEqual(len(regions), 2)

        for region in regions:
            self.assertIn("name", region)
            self.assertIn("number_countries", region)
            self.assertIn("total_population", region)

    def test_aggregations_are_correct(self):
        resp = self.client.get("/countries/stats/")
        regions = {r["name"]: r for r in resp.json()["regions"]}

        self.assertEqual(regions["Africa"]["number_countries"], 2)
        self.assertEqual(regions["Africa"]["total_population"], 250_000_000)

        self.assertEqual(regions["Europe"]["number_countries"], 1)
        self.assertEqual(regions["Europe"]["total_population"], 67_000_000)

    def test_name_filter_icontains(self):
        # Filter should match case-insensitively and by substring
        resp = self.client.get("/countries/stats/?name=afr")
        regions = resp.json()["regions"]
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0]["name"], "Africa")

    def test_pagination_parameters(self):
        # per_page=1 should yield 2 total pages for our 2 regions
        resp = self.client.get("/countries/stats/?per_page=1&page=1")
        payload = resp.json()
        self.assertEqual(payload["meta"]["per_page"], 1)
        self.assertEqual(payload["meta"]["total_pages"], 2)
        self.assertEqual(payload["meta"]["page"], 1)
        self.assertEqual(len(payload["regions"]), 1)

        resp2 = self.client.get("/countries/stats/?per_page=1&page=2")
        payload2 = resp2.json()
        self.assertEqual(payload2["meta"]["page"], 2)
        self.assertEqual(len(payload2["regions"]), 1)

    def test_invalid_params_are_rejected(self):
        # per_page too large (validator max=100 is fine; test a negative page)
        resp = self.client.get("/countries/stats/?page=0")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())
