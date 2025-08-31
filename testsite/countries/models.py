from django.db import models


class Region(models.Model):
    """
    Represents a geographical region containing multiple countries.
    """
    name = models.CharField(max_length=100)

    class Meta:
        indexes = [
            models.Index(fields=["name"], name="region_name_idx"),
        ]
        ordering = ["name"]
        verbose_name = "Region"
        verbose_name_plural = "Regions"

    def __str__(self):
        return self.name

class Country(models.Model):
    """
    Represents a country within a region, with ISO codes and population.
    """
    name = models.CharField(max_length=100)
    alpha2Code = models.CharField(max_length=2)
    alpha3Code = models.CharField(max_length=3)
    population = models.IntegerField()
    region = models.ForeignKey(
        "Region",
        on_delete=models.CASCADE,
        related_name="countries",
    )

    class Meta:
        indexes = [
            models.Index(fields=["region"], name="country_region_idx"),
            models.Index(fields=["population"], name="country_population_idx"),
        ]
        ordering = ["name"]
        verbose_name = "Country"
        verbose_name_plural = "Countries"

    def __str__(self):
        return self.name
