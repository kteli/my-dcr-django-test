from django.db import models
from django.core.validators import RegexValidator


# --- Validators ---
alpha2_validator = RegexValidator(
    r"^[A-Z]{2}$", "alpha2Code must be 2 uppercase letters"
)
alpha3_validator = RegexValidator(
    r"^[A-Z]{3}$", "alpha3Code must be 3 uppercase letters"
)


class Region(models.Model):
    """
    Represents a geographical region containing multiple countries.
    """
    name = models.CharField(max_length=100, unique=True, db_index=True)

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
    Represents a country within a region, with ISO codes, population, capital, and TLDs.
    """
    name = models.CharField(max_length=100, unique=True, db_index=True)

    alpha2Code = models.CharField(
        max_length=2, unique=True, db_index=True, validators=[alpha2_validator]
    )
    alpha3Code = models.CharField(
        max_length=3, unique=True, db_index=True, validators=[alpha3_validator]
    )

    # Use BigIntegerField to handle very large populations safely
    population = models.BigIntegerField()

    region = models.ForeignKey(
        "Region",
        on_delete=models.CASCADE,
        related_name="countries",
    )

    # Django 2.2 does not have JSONField so we store as JSON-encoded text string consistently
    topLevelDomain = models.TextField(default="[]")

    capital = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["region"], name="country_region_idx"),
            models.Index(fields=["population"], name="country_population_idx"),
            models.Index(fields=["capital"], name="country_capital_idx"),
        ]
        ordering = ["name"]
        verbose_name = "Country"
        verbose_name_plural = "Countries"

    def save(self, *args, **kwargs):
        # Normalize codes to uppercase
        if self.alpha2Code:
            self.alpha2Code = self.alpha2Code.upper()
        if self.alpha3Code:
            self.alpha3Code = self.alpha3Code.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
