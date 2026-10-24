"""
tinyfish_client.py
Part of TestPrioritize AI.

HTTP client for the official TinyFish Search REST API.
Retrieves external web intelligence, release notes, and documentation
safely with error handling and without exposing credentials.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

DEFAULT_TINYFISH_ENDPOINT = "https://api.search.tinyfish.ai"
DEFAULT_TIMEOUT_SECONDS = 10.0

STATUS_SUCCESS = "success"
STATUS_NO_RESULTS = "no_results"
STATUS_MISSING_KEY = "missing_key"
STATUS_HTTP_ERROR = "http_error"
STATUS_TIMEOUT = "timeout"
STATUS_NETWORK_ERROR = "network_error"
STATUS_INVALID_JSON = "invalid_json"


@dataclass(frozen=True)
class SearchResultItem:
    """
    Represents an individual search result returned by TinyFish.

    Attributes:
        title: Title of the web page or release document.
        url: Validated HTTP/HTTPS source URL.
        snippet: Text excerpt or content snippet.
        site_name: Domain or publisher name.
        position: Rank position in the search response.
    """
    title: str
    url: str
    snippet: str
    site_name: str = ""
    position: Optional[int] = None


@dataclass(frozen=True)
class TinyFishSearchResponse:
    """
    Typed response returned by search_tinyfish.

    Attributes:
        query: The search query string submitted.
        status: Status code indicating success or specific failure reason.
        results: List of SearchResultItem objects.
        total_results: Total count of results reported by the API.
        error_message: Human-readable error description, if any.
    """
    query: str
    status: str
    results: List[SearchResultItem] = field(default_factory=list)
    total_results: int = 0
    error_message: Optional[str] = None


def get_api_key(explicit_key: Optional[str] = None) -> Optional[str]:
    """
    Safely retrieves the TinyFish API key from argument or environment variable.
    Never prints or logs the key value.
    """
    if explicit_key and isinstance(explicit_key, str) and explicit_key.strip():
        candidate = explicit_key.strip()
    else:
        candidate = os.getenv("TINYFISH_API_KEY", "").strip()
        if not candidate or candidate == "your_tinyfish_api_key_here":
            try:
                from dotenv import load_dotenv
                load_dotenv(override=True)
                candidate = os.getenv("TINYFISH_API_KEY", "").strip()
            except Exception:
                pass

    if not candidate or candidate == "your_tinyfish_api_key_here":
        return None
    return candidate


def is_valid_url(url: str) -> bool:
    """
    Validates that a URL is a well-formed HTTP or HTTPS URL.
    """
    if not isinstance(url, str) or not url.strip():
        return False
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def search_tinyfish(
    query: str,
    api_key: Optional[str] = None,
    endpoint: str = DEFAULT_TINYFISH_ENDPOINT,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    session: Optional[requests.Session] = None
) -> TinyFishSearchResponse:
    """
    Performs a web search via the TinyFish Search REST API.

    Args:
        query: Search query string.
        api_key: Optional explicit API key; defaults to TINYFISH_API_KEY env var.
        endpoint: TinyFish API endpoint URL.
        timeout: HTTP request timeout in seconds.
        session: Optional requests.Session for connection reuse or testing.

    Returns:
        TinyFishSearchResponse containing parsed results or graceful error status.
    """
    if not isinstance(query, str) or not query.strip():
        return TinyFishSearchResponse(
            query=query,
            status=STATUS_NO_RESULTS,
            results=[],
            total_results=0,
            error_message="Query string must be non-empty."
        )

    resolved_key = get_api_key(api_key)
    if not resolved_key:
        return TinyFishSearchResponse(
            query=query,
            status=STATUS_MISSING_KEY,
            results=[],
            total_results=0,
            error_message="TINYFISH_API_KEY environment variable is not configured."
        )

    headers = {
        "X-API-Key": resolved_key,
        "Accept": "application/json",
        "User-Agent": "TestPrioritizeAI/1.0"
    }
    params = {"query": query.strip()}

    http_client = session if session is not None else requests

    try:
        response = http_client.get(
            endpoint,
            headers=headers,
            params=params,
            timeout=timeout
        )
    except requests.Timeout:
        return TinyFishSearchResponse(
            query=query,
            status=STATUS_TIMEOUT,
            results=[],
            total_results=0,
            error_message=f"Request to TinyFish timed out after {timeout} seconds."
        )
    except requests.RequestException as exc:
        return TinyFishSearchResponse(
            query=query,
            status=STATUS_NETWORK_ERROR,
            results=[],
            total_results=0,
            error_message=f"Network error communicating with TinyFish: {exc}"
        )

    if response.status_code != 200:
        return TinyFishSearchResponse(
            query=query,
            status=STATUS_HTTP_ERROR,
            results=[],
            total_results=0,
            error_message=f"TinyFish returned HTTP {response.status_code}."
        )

    try:
        data = response.json()
    except Exception as exc:
        return TinyFishSearchResponse(
            query=query,
            status=STATUS_INVALID_JSON,
            results=[],
            total_results=0,
            error_message=f"Failed to parse JSON response from TinyFish: {exc}"
        )

    if not isinstance(data, dict):
        return TinyFishSearchResponse(
            query=query,
            status=STATUS_INVALID_JSON,
            results=[],
            total_results=0,
            error_message="Unexpected response payload: root JSON is not an object."
        )

    raw_results = data.get("results")
    if not isinstance(raw_results, list):
        return TinyFishSearchResponse(
            query=query,
            status=STATUS_NO_RESULTS,
            results=[],
            total_results=0,
            error_message=None
        )

    parsed_items: List[SearchResultItem] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue

        raw_url = str(item.get("url", "")).strip()
        # Security: preserve and validate URL
        if not is_valid_url(raw_url):
            continue

        title = str(item.get("title", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        site_name = str(item.get("site_name", "")).strip()
        pos = item.get("position")
        position = int(pos) if isinstance(pos, (int, float)) else None

        parsed_items.append(
            SearchResultItem(
                title=title,
                url=raw_url,
                snippet=snippet,
                site_name=site_name,
                position=position
            )
        )

    if not parsed_items:
        return TinyFishSearchResponse(
            query=query,
            status=STATUS_NO_RESULTS,
            results=[],
            total_results=0,
            error_message=None
        )

    total_results = data.get("total_results", len(parsed_items))
    if not isinstance(total_results, int):
        total_results = len(parsed_items)

    return TinyFishSearchResponse(
        query=query,
        status=STATUS_SUCCESS,
        results=parsed_items,
        total_results=total_results,
        error_message=None
    )
