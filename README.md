# Countries Data Import and Statistics

This Django application manages country and region data, providing a management command to import data from a remote API and an endpoint to retrieve region-level statistics. The implementation includes three key features, corresponding to Exercises 1, 2, and 3, with a focus on modularity, performance, and robust error handling.

## Features

### Exercise 1: Region Statistics Endpoint
- **Endpoint**: `/countries/stats/`
  - Returns aggregated statistics for regions, including:
    - Region name
    - Number of countries in the region
    - Total population across all countries in the region
  - Supports optional filtering by region name (case-insensitive) via a `name` query parameter.
  - Implements pagination for large datasets, with metadata (e.g., page number, total pages) included in the response.
  - Returns a compact JSON response with execution time for performance monitoring.
- **Service Layer**:
  - The `get_region_stats` service in `countries/services/region_stats.py` uses Django's ORM with:
  
    - `Count("countries")` and `Sum("countries__population")` annotations for efficient aggregation.
    - Validation of the `name_filter` parameter to ensure safe filtering.
  - Returns a clean dictionary for JSON serialization.
- **View Updates**:
  - The `stats` view validates query parameters using a `parse_stats_query` function.
  - Handles non-GET requests with appropriate error responses.
  - Uses `paginate_queryset` and `page_meta` for consistent pagination.
  - Includes robust error handling with `ValidationError` for invalid inputs.
- **Model and Database Enhancements**:
  - Added `Meta` options to the `Country` model:
    - `ordering = ["name"]` for consistent display.
    - `verbose_name` and `verbose_name_plural` for improved admin interface usability.
  - Ensured `Region` creation uses `full_clean` for validation.
  - Added database indexes for performance:
    - Index on `Region.name` to optimize `icontains` filtering and ordering.
    - Unique constraints/indexes on `Country.alpha2Code` and `Country.alpha3Code` for data integrity and fast lookups.
  - Centralized data validation with `CountryRowForm` to ensure consistent input validation.

### Exercise 2: API Integration
- **Management Command**: `python manage.py update_country_listing`
  - Updated to fetch country data from the remote JSON API at `https://storage.googleapis.com/dcr-django-test/countries.json` instead of a local file.
  - Implemented in the `APIClient` service (`countries/services/api_client.py`):
    - Uses `requests` for HTTP requests with a 10-second timeout.
    - Implements retry logic with `tenacity` (3 attempts, 5-second wait) for transient network errors.
    - Validates the API response to ensure it’s a non-empty JSON array.
    - Supports saving the response to `api_response.json` for debugging via the `--save-response` flag.
    - Configurable API URL via the `COUNTRY_API_URL` environment variable.
  - Handles errors gracefully, raising `CommandError` for network issues (`RequestException`) or invalid JSON (`ValueError`).

### Exercise 3: Store Additional Data
- Enhanced the `update_country_listing` command to import and store two additional fields from the API:
  - `topLevelDomain`: Stored as a list (e.g., in a `TextField` due to form module compatibility).
  - `capital`: Stored as a string.
- Added the `DataValidator` service (`countries/services/data_validator.py`):
  - Validates `topLevelDomain` (defaults to an empty list if missing) and `capital` (defaults to an empty string).
  - Uses `CountryRowForm` for centralized validation, raising `CountryDataValidationError` on invalid input.
- Modified the `DatabaseManager` service (`countries/services/database_manager.py`):
  - Includes `topLevelDomain` and `capital` in bulk create and update operations for the `Country` model.
  - Ensures data integrity with validation and unique constraints.

## Additional Improvements
- **Modular Architecture**:
  - Split the command logic into three reusable services:
    - `APIClient`: Handles API fetching and parsing.
    - `DataValidator`: Manages data validation and transformation.
    - `DatabaseManager`: Encapsulates database operations (reset, region creation, country create/update).
  - The `update_country_listing` command orchestrates these services, keeping the code lean and focused.
- **Readability**:
  - Added comprehensive docstrings for all methods and classes.
  - Used consistent logging with `logger.debug`, `logger.info`, `logger.warning`, and `logger.error`.
  - Included an optional `tqdm` progress bar for user feedback during imports.
- **Performance**:
  - Maintained batch processing with a configurable `--batch-size` (default: 1000) to balance memory usage and performance.
  - Added indexes to improve query performance for filtering and lookups.
- **Robustness**:
  - Improved transaction handling with `contextlib.suppress()` for dry-run mode, ensuring compatibility with older Django versions (avoiding the `durable` parameter).
  - Validated API response keys to catch malformed data early.
  - Enhanced error handling for network, validation, and database errors, with descriptive messages.
- **Usability**:
  - Added summary statistics (created, updated, skipped counts) after imports.
  - Improved command help text and argument descriptions for clarity.
  - Supported `--dry-run` to simulate imports without committing changes.
- **Testability**:
  - Structured services for easy unit testing with Django’s `TestCase` and mocking libraries.
- **Caching**:
  - added caching at view level


## Installation

Follow these steps to set up the Django application for importing country data and accessing region statistics.

### Prerequisites
- **Python**: Version 3.8.18 
- **Django**: Compatible with older versions (e.g., pre-2.2.17)
- **Dependencies**:
  - `requests`: For API requests
  - `tenacity`: For retry logic on network requests
  - `tqdm` : For progress bar during imports
- **Database**: A configured database (e.g., SQLite, PostgreSQL) compatible with Django

### Steps

1. **Clone the Repository** (if applicable):
   Clone the project repository to your local machine:
   ```bash
   git clone <https://github.com/kteli/my-dcr-django-test.git>
    ```

2. **Set Up a Virtual Environment (recommended)**:
Create and activate a virtual environment to manage dependencies:

```bash
python3 -m venv dcr-django-test-env
source dcr-django-test-env/bin/activate  # On Windows: dcr-django-test-env\Scripts\activate
```

3. **Install Dependencies:**
Install the required  packages using pip:

```bash
    pip install -r requirements.txt
    
    cd testsite 
```

4. **Apply Database Migrations:**
Create and apply migrations to set up the Country and Region models with the required fields and indexes:

```bash
python manage.py makemigrations
python manage.py migrate
```

# Test the Setup:
Run the Django development server to verify the setup:

## Running Tests

This project includes a full test suite for the `countries` app, covering:

- `/countries/stats/` API endpoint
- Data validation (`DataValidator`, `CountryRowForm`)
- Management command `update_country_listing`


### Run all tests

```bash
python manage.py test -v 2
```

## Import Command Options

    - python manage.py update_country_listing
    - python manage.py update_country_listing --dry-run
    - python manage.py update_country_listing --reset
    - python manage.py update_country_listing --batch-size=500 --no-progress
    - python manage.py update_country_listing --save-response

The `update_country_listing` management command supports several optional flags to customize its behavior. These options enhance flexibility, debugging, and performance tuning.

- **`--batch-size <number>`**:
  - Specifies the number of records to process in each database batch (default: 1000).
  - Use to balance memory usage and performance for large datasets.
  - Example: Process 500 records per batch for lower memory usage:
    ```bash
    python manage.py update_country_listing --batch-size 500
    ```

- **`--dry-run`**:
  - Simulates the import process without committing changes to the database.
  - Useful for testing the command’s behavior or validating data without modifying the database.
  - Example: Test the import without saving data:
    ```bash
    python manage.py update_country_listing --dry-run
    ```
    ![alt text](<Screenshot 2025-08-31 at 03.38.28.png>)

- **`--reset`**:
  - Clears the `Country` and `Region` tables before importing new data.
  - Ensures a fresh start, removing existing data to avoid conflicts.
  - Example: Reset the database and import fresh data:
    ```bash
    python manage.py update_country_listing --reset
    ```
    ![alt text](<Screenshot 2025-08-31 at 03.36.51.png>)

- **`--save-response`**:
  - Saves the raw API response to `api_response.json` for debugging.
  - Helpful for inspecting the data returned by the API without processing it.
  - Example: Save the API response to a file:
    ```bash
    python manage.py update_country_listing --save-response
    ```

### Combining Options
You can combine these options for specific use cases. For example, to test a low-memory import with a reset and save the API response:
```bash
python manage.py update_country_listing --batch-size 200 --dry-run --reset --save-response
```

