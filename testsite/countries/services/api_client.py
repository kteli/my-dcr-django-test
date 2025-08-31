import json, logging,os,requests
from typing import List, Dict, Any
from requests.exceptions import RequestException, Timeout, HTTPError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

logger = logging.getLogger(__name__)


def _retryable(exc: Exception) -> bool:
    """
    Decide if an exception should trigger a retry.
    Retries on connection issues, timeouts, or 5xx responses.
    """
    if isinstance(exc, (Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, HTTPError) and exc.response is not None:
        return 500 <= exc.response.status_code < 600
    return False


class APIClient:
    """
    Service for fetching data from a remote JSON API.
    Default URL comes from env var COUNTRY_API_URL or falls back to the assignment URL.
    """

    def __init__(
        self,
        url: str = os.getenv(
            "COUNTRY_API_URL",
            "https://storage.googleapis.com/dcr-django-test/countries.json",
        ),
    ):
        self.url = url

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception(_retryable),
        reraise=True,
    )
    def fetch_data(self, save_response: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch country data from the API.

        Args:
            save_response: If True, save the API response to a local file.

        Returns:
            List of country dicts.

        Raises:
            ValueError: If the API response is not a valid list.
            RequestException: On network errors or non-2xx status.
        """
        logger.debug(f"Fetching country data from {self.url}")
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list):
                raise ValueError("API response is not a valid JSON array")

            if not data:
                logger.warning("API returned empty data")
                raise ValueError("Empty response from API")

            logger.info(f"Fetched {len(data)} country records")

            if save_response:
                with open("api_response.json", "w") as f:
                    json.dump(data, f, indent=2)
                logger.debug("Saved API response to api_response.json")

            return data

        except RequestException as e:
            logger.error(f"Network error fetching data: {e}")
            raise
        except ValueError as e:
            logger.error(f"Invalid API response: {e}")
            raise
