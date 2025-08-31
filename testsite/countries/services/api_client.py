import json
import logging
import os
from typing import List, Dict, Any

import requests
from requests.exceptions import RequestException
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

logger = logging.getLogger(__name__)

class APIClient:
    """Service for fetching data from a remote JSON API."""
    
    def __init__(self, url: str = os.getenv("COUNTRY_API_URL", "https://storage.googleapis.com/dcr-django-test/countries.json")):
        self.url = url

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(5),
        retry=retry_if_exception_type(requests.exceptions.ConnectionError),
    )
    def fetch_data(self, save_response: bool = False) -> List[Dict[str, Any]]:
        """Fetch country data from the API.

        Args:
            save_response: If True, save the API response to a file.

        Returns:
            List of dictionaries containing country data.

        Raises:
            ValueError: If the API response is invalid.
            RequestException: If the network request fails.
        """
        logger.debug(f"Fetching data from {self.url}")
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list):
                raise ValueError("API response is not a valid JSON array")
            if not data:
                logger.warning("No data received from API")
                raise ValueError("API returned empty data")

            logger.info(f"Fetched {len(data)} records")

            if save_response:
                with open("api_response.json", "w") as f:
                    json.dump(data, f, indent=2)
                    logger.debug("Saved API response to api_response.json")

            return data
        except RequestException as e:
            logger.error(f"Network error while fetching data: {e}")
            raise
        except ValueError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise