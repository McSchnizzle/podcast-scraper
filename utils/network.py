#!/usr/bin/env python3
"""
Network Utilities with Retry Logic
Provides robust HTTP requests with exponential backoff and jitter
"""

import logging
import random
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


def get_with_backoff(
    url: str,
    tries: int = 4,
    base_delay: float = 0.5,
    timeout: int = 10,
    headers: Optional[Dict[str, str]] = None,
) -> requests.Response:
    """
    Fetch URL with exponential backoff and jitter

    Args:
        url: URL to fetch
        tries: Maximum number of attempts (default 4)
        base_delay: Base delay in seconds for exponential backoff
        timeout: Request timeout in seconds
        headers: Optional HTTP headers

    Returns:
        requests.Response object

    Raises:
        requests.RequestException: If all retries fail
    """
    if headers is None:
        headers = {
            "User-Agent": "PodcastDigest/2.0 (+https://github.com/McSchnizzle/podcast-scraper)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        }

    last_exception = None

    for attempt in range(tries):
        try:
            logger.debug(f"Attempting fetch ({attempt + 1}/{tries}): {url}")

            response = requests.get(
                url, timeout=timeout, headers=headers, allow_redirects=True
            )

            # Check for HTTP errors
            response.raise_for_status()

            logger.debug(f"✅ Successfully fetched {url} in {attempt + 1} attempt(s)")
            return response

        except requests.RequestException as e:
            last_exception = e

            if attempt == tries - 1:
                # Last attempt failed
                logger.error(f"❌ All {tries} attempts failed for {url}: {e}")
                raise

            # Calculate delay with exponential backoff + jitter
            delay = base_delay * (2**attempt) + random.random() * 0.2

            logger.warning(f"⚠️  Attempt {attempt + 1}/{tries} failed for {url}: {e}")
            logger.debug(f"Retrying in {delay:.2f} seconds...")

            time.sleep(delay)

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    else:
        raise requests.RequestException(f"Failed to fetch {url} after {tries} attempts")


def post_with_backoff(
    url: str,
    data: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    tries: int = 3,
    base_delay: float = 0.5,
    timeout: int = 30,
    headers: Optional[Dict[str, str]] = None,
) -> requests.Response:
    """
    POST request with exponential backoff and jitter

    Args:
        url: URL to POST to
        data: Form data to send
        json: JSON data to send
        tries: Maximum number of attempts
        base_delay: Base delay for backoff
        timeout: Request timeout
        headers: Optional HTTP headers

    Returns:
        requests.Response object
    """
    if headers is None:
        headers = {
            "User-Agent": "PodcastDigest/2.0 (+https://github.com/McSchnizzle/podcast-scraper)"
        }

    last_exception = None

    for attempt in range(tries):
        try:
            logger.debug(f"POST attempt ({attempt + 1}/{tries}): {url}")

            response = requests.post(
                url,
                data=data,
                json=json,
                timeout=timeout,
                headers=headers,
                allow_redirects=True,
            )

            response.raise_for_status()

            logger.debug(f"✅ POST successful to {url}")
            return response

        except requests.RequestException as e:
            last_exception = e

            if attempt == tries - 1:
                logger.error(f"❌ All POST attempts failed for {url}: {e}")
                raise

            delay = base_delay * (2**attempt) + random.random() * 0.2
            logger.warning(f"⚠️  POST attempt {attempt + 1}/{tries} failed: {e}")
            logger.debug(f"Retrying POST in {delay:.2f} seconds...")

            time.sleep(delay)

    if last_exception:
        raise last_exception
    else:
        raise requests.RequestException(f"POST failed to {url} after {tries} attempts")


def is_network_error(exception: Exception) -> bool:
    """
    Check if an exception is a network-related error that should trigger retry

    Args:
        exception: Exception to check

    Returns:
        True if the exception is a retryable network error
    """
    if isinstance(exception, requests.exceptions.ConnectionError):
        return True
    if isinstance(exception, requests.exceptions.Timeout):
        return True
    if isinstance(exception, requests.exceptions.ReadTimeout):
        return True
    if isinstance(exception, requests.exceptions.ConnectTimeout):
        return True

    # Check for specific HTTP status codes that should trigger retry
    if isinstance(exception, requests.exceptions.HTTPError):
        if hasattr(exception, "response") and exception.response:
            status_code = exception.response.status_code
            # Retry on server errors (5xx) and rate limiting (429)
            if status_code >= 500 or status_code == 429:
                return True

    return False


def get_safe_filename(url: str) -> str:
    """
    Convert URL to a safe filename by removing/replacing problematic characters

    Args:
        url: URL to convert

    Returns:
        Safe filename string
    """
    import re
    from urllib.parse import urlparse

    parsed = urlparse(url)

    # Create filename from domain and path
    domain = parsed.netloc.replace("www.", "")
    path = parsed.path.replace("/", "_").replace("\\", "_")

    # Remove problematic characters
    filename = f"{domain}{path}"
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    filename = re.sub(r"_+", "_", filename)  # Collapse multiple underscores
    filename = filename.strip("_")  # Remove leading/trailing underscores

    # Limit length
    if len(filename) > 100:
        filename = filename[:100]

    return filename or "unknown"


def validate_url(url: str) -> bool:
    """
    Basic URL validation

    Args:
        url: URL to validate

    Returns:
        True if URL appears valid
    """
    from urllib.parse import urlparse

    if not url or not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def get_content_type(response: requests.Response) -> str:
    """
    Extract content type from response headers

    Args:
        response: requests.Response object

    Returns:
        Content type string (e.g., 'application/rss+xml')
    """
    content_type = response.headers.get("Content-Type", "").lower()

    # Split on semicolon to remove charset info
    if ";" in content_type:
        content_type = content_type.split(";")[0].strip()

    return content_type


# Backwards compatibility aliases
fetch_with_retry = get_with_backoff
robust_get = get_with_backoff
