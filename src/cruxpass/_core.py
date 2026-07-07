"""Shared building blocks for the sync and async CruxPass clients."""

import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import parse_qsl, quote, urlsplit

import httpx

type Temporal = date | datetime | str

DEFAULT_BASE_URL = "https://cruxpass.com"
DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_RETRIES = 2
API_KEY_ENV_VAR = "CRUXPASS_API_KEY"
BASE_URL_ENV_VAR = "CRUXPASS_BASE_URL"

# CruxPass event and schedule writes are idempotent upserts keyed by
# external_id, so retrying these statuses is safe across the API surface.
RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})
RETRYABLE_EXCEPTIONS = (httpx.ConnectError, httpx.ConnectTimeout)


class CruxPassError(Exception):
    """Base exception for CruxPass client errors."""


class APIError(CruxPassError):
    """Raised when the CruxPass API returns an unsuccessful response."""

    def __init__(
        self, status_code: int, message: str, response: httpx.Response
    ) -> None:
        super().__init__(f"CruxPass API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.response = response


class AuthenticationError(APIError):
    """Raised for 401 and 403 responses."""


class NotFoundError(APIError):
    """Raised for 404 responses."""


class RateLimitError(APIError):
    """Raised for 429 responses that persist after retries."""


class ServerError(APIError):
    """Raised for 5xx responses that persist after retries."""


@dataclass(frozen=True, slots=True)
class FeedResponse:
    """Public subscriber feed response with cache validator metadata."""

    status_code: int
    text: str
    etag: str | None
    last_modified: str | None
    headers: httpx.Headers


def resolve_api_key(api_key: str | None) -> str:
    resolved = api_key or os.environ.get(API_KEY_ENV_VAR, "")
    if not resolved:
        raise ValueError(
            f"api_key is required; pass it explicitly or set {API_KEY_ENV_VAR}"
        )
    return resolved


def resolve_base_url(base_url: str | None) -> str:
    resolved = base_url or os.environ.get(BASE_URL_ENV_VAR, "") or DEFAULT_BASE_URL
    return resolved.rstrip("/")


def error_for_response(response: httpx.Response) -> APIError:
    status = response.status_code
    message = response_message(response)
    if status in (401, 403):
        return AuthenticationError(status, message, response)
    if status == 404:
        return NotFoundError(status, message, response)
    if status == 429:
        return RateLimitError(status, message, response)
    if status >= 500:
        return ServerError(status, message, response)
    return APIError(status, message, response)


def response_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, str):
            return detail
    return str(data)


def retry_delay(attempt: int, retry_after: str | None) -> float:
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    return min(0.5 * (2**attempt), 8.0)


def serialize_temporal(value: Temporal) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        serialized = value.isoformat()
        if value.tzinfo == UTC:
            return serialized.replace("+00:00", "Z")
        return serialized
    return value.isoformat()


def quote_path_part(value: str) -> str:
    return quote(value, safe="")


def normalize_path(path: str) -> str:
    if not path.startswith("/"):
        return f"/{path}"
    return path


def json_body(response: httpx.Response) -> Any:
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def list_response_page(data: Any) -> tuple[list[dict[str, Any]], str | None]:
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        next_url = data.get("next")
        if next_url is not None and not isinstance(next_url, str):
            raise TypeError("CruxPass paginated response 'next' must be a string.")
        return data["results"], next_url
    raise TypeError("Expected a CruxPass list response.")


def params_from_next_url(next_url: str) -> dict[str, str]:
    return dict(parse_qsl(urlsplit(next_url).query, keep_blank_values=True))


def feed_path(token: str) -> str:
    return f"/f/{quote_path_part(token)}.ics"


def feed_headers(etag: str | None, modified_since: str | None) -> dict[str, str]:
    headers = {"Accept": "text/calendar"}
    if etag is not None:
        headers["If-None-Match"] = etag
    if modified_since is not None:
        headers["If-Modified-Since"] = modified_since
    return headers


def feed_response(response: httpx.Response) -> FeedResponse:
    return FeedResponse(
        status_code=response.status_code,
        text=response.text,
        etag=response.headers.get("ETag"),
        last_modified=response.headers.get("Last-Modified"),
        headers=response.headers,
    )


def event_payload(
    *,
    external_id: str,
    summary: str,
    start: Temporal,
    end: Temporal,
    description: str = "",
    location: str = "",
    all_day: bool = False,
    status: str = "confirmed",
    busy: bool = True,
) -> dict[str, Any]:
    return {
        "external_id": external_id,
        "summary": summary,
        "description": description,
        "location": location,
        "start": serialize_temporal(start),
        "end": serialize_temporal(end),
        "all_day": all_day,
        "status": status,
        "busy": busy,
    }


def schedule_payload(
    *,
    external_id: str,
    summary: str,
    first_start: Temporal,
    first_end: Temporal,
    frequency: str,
    description: str = "",
    location: str = "",
    all_day: bool = False,
    status: str = "confirmed",
    busy: bool = True,
    interval: int = 1,
    count: int | None = None,
    until: Temporal | None = None,
    window_months: int = 6,
) -> dict[str, Any]:
    return {
        "external_id": external_id,
        "summary": summary,
        "description": description,
        "location": location,
        "first_start": serialize_temporal(first_start),
        "first_end": serialize_temporal(first_end),
        "all_day": all_day,
        "status": status,
        "busy": busy,
        "frequency": frequency,
        "interval": interval,
        "count": count,
        "until": serialize_temporal(until) if until is not None else None,
        "window_months": window_months,
    }


def exception_payload(
    *,
    occurrence_number: int,
    action: str,
    start: Temporal | None = None,
    end: Temporal | None = None,
    summary: str = "",
    description: str = "",
    location: str = "",
) -> dict[str, Any]:
    return {
        "occurrence_number": occurrence_number,
        "action": action,
        "start": serialize_temporal(start) if start is not None else None,
        "end": serialize_temporal(end) if end is not None else None,
        "summary": summary,
        "description": description,
        "location": location,
    }


def subscriber_payload(
    *,
    feeds: Sequence[str],
    label: str = "",
    email: str = "",
    calendar_name: str = "",
) -> dict[str, Any]:
    return {
        "label": label,
        "email": email,
        "calendar_name": calendar_name,
        "feeds": list(feeds),
    }


def update_payload(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def feed_update_payload(
    *,
    name: str | None,
    group: str | None,
    color: str | None,
    clear_group: bool,
) -> dict[str, Any]:
    if group is not None and clear_group:
        raise ValueError("group and clear_group cannot both be set")
    payload = update_payload(name=name, group=group, color=color)
    if clear_group:
        payload["group"] = None
    return payload


def subscriber_update_payload(
    *,
    label: str | None,
    email: str | None,
    calendar_name: str | None,
    feeds: Sequence[str] | None,
) -> dict[str, Any]:
    payload = update_payload(label=label, email=email, calendar_name=calendar_name)
    if feeds is not None:
        payload["feeds"] = list(feeds)
    return payload
