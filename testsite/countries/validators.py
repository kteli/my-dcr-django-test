from django import forms
from django.core.exceptions import ValidationError
import re, json, logging
from django.core.validators import RegexValidator

logger = logging.getLogger(__name__)

_only_letters_spaces_hyphens = RegexValidator(
    regex=r'^[A-Za-z\s-]+$',
    message="Name may contain only letters, spaces, or hyphens.",
)

class StatsQueryForm(forms.Form):
    page = forms.IntegerField(min_value=1, required=False)
    per_page = forms.IntegerField(min_value=1, max_value=100, required=False)
    name = forms.CharField(
        required=False,
        max_length=100,
        strip=True,
        validators=[_only_letters_spaces_hyphens],
    )

def clean_name(self):
        """
        Make empty name -> None, and ensure at least one letter if provided.
        """
        name = self.cleaned_data.get("name", "")
        if name == "":
            return None
        if not re.search(r"[A-Za-z]", name):
            raise ValidationError("Name must include at least one letter.")
        return name

def parse_stats_query(request, default_page=1, default_per_page=10):
    """
    Validate and normalize ?page=, ?per_page=, ?name= from request.GET.
    Returns (page, per_page, name_filter).
    Raises ValidationError on bad input.
    """
    data = {
        "page": request.GET.get("page", default_page),
        "per_page": request.GET.get("per_page", default_per_page),
        "name": request.GET.get("name", "").strip(),
    }
    form = StatsQueryForm(data)
    if not form.is_valid():
        # Pack all field errors into one ValidationError for the view to handle
        raise ValidationError(form.errors.get_json_data())

    page = form.cleaned_data.get("page") or default_page
    per_page = form.cleaned_data.get("per_page") or default_per_page
    name = form.cleaned_data.get("name")  # None if not provided
    return page, per_page, name

class CountryRowForm(forms.Form):
    name = forms.CharField(strip=True, min_length=1, max_length=200)
    region = forms.CharField(strip=True, min_length=1, max_length=100)
    alpha2Code = forms.CharField(strip=True, min_length=2, max_length=2)
    alpha3Code = forms.CharField(strip=True, min_length=3, max_length=3)
    population = forms.IntegerField(min_value=0)
    topLevelDomain = forms.CharField(max_length=1000, required=True)
    capital = forms.CharField(required=False, max_length=100, strip=True)

    def clean_alpha2Code(self):
        return self.cleaned_data["alpha2Code"].upper()

    def clean_alpha3Code(self):
        return self.cleaned_data["alpha3Code"].upper()
    
    def clean_topLevelDomain(self):
        value = self.cleaned_data.get("topLevelDomain")
        country = self.cleaned_data.get("name")

        # Parse string to list if needed
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise ValidationError("topLevelDomain must be a valid JSON list.")

        if not isinstance(value, list):
            raise ValidationError("topLevelDomain must be a list.")

        tld_pattern = re.compile(r'^\.[a-zA-Z]{2,}$')
        cleaned = []

        for tld in value:
            if not isinstance(tld, str):
                continue
            tld = tld.strip()
            if not tld:
                #  Log the issue, but don't block the record
                logger.warning(f"❌ Empty top-level domain value detected: {value} for {country}")
                continue
            if not tld_pattern.match(tld):
                logger.warning(f"❌ Invalid top-level domain format: {tld} for {country}")
                continue
            cleaned.append(tld)

        # Allow saving even if cleaned is empty
        return json.dumps(cleaned)


    def clean_capital(self):
        val = self.cleaned_data.get("capital")
        # Normalize empty string to None (since model allows null=True)
        return val if val else None