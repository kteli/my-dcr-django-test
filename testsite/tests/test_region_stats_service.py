from django.test import TestCase
from countries.models import Region, Country
from countries.services.region_stats import get_region_stats

class RegionStatsServiceTests(TestCase):
    def setUp(self):
        # Set up test data
        africa = Region.objects.create(name="Africa")
        europe = Region.objects.create(name="Europe")

        # Create countries related to regions
        Country.objects.create(name="Nigeria", alpha2Code="NG", alpha3Code="NGA", population=200_000_000, region=africa)
        Country.objects.create(name="Kenya", alpha2Code="KE", alpha3Code="KEN", population=50_000_000, region=africa)
        Country.objects.create(name="Egypt", alpha2Code="EG", alpha3Code="EGY", population=100_000_000, region=africa)
        Country.objects.create(name="Germany", alpha2Code="DE", alpha3Code="DEU", population=80_000_000, region=europe)
        Country.objects.create(name="France", alpha2Code="FR", alpha3Code="FRA", population=67_000_000, region=europe)

    def test_get_region_stats_qs(self):
        # Call the service function
        qs = get_region_stats().values("name", "number_countries", "total_population")
        
        # Convert QuerySet to list for easy checking
        rows = list(qs)

        # Assert that Africa has 3 countries with a total population of 350,000,000
        africa = next(r for r in rows if r["name"] == "Africa")
        self.assertEqual(africa["number_countries"], 3)
        self.assertEqual(africa["total_population"], 350_000_000)

        # Assert that Europe has 2 countries with a total population of 147,000,000
        europe = next(r for r in rows if r["name"] == "Europe")
        self.assertEqual(europe["number_countries"], 2)
        self.assertEqual(europe["total_population"], 147_000_000)
