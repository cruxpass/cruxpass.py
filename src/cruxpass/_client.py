from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping, Optional, Sequence, Union
from urllib.parse import quote

import requests


Temporal = Union[date, datetime, str]


class CruxPassError(Exception):
    """Base exception for CruxPass client errors."""


class APIError(CruxPassError):
    """Raised when the CruxPass API returns an unsuccessful response."""

    def __init__(self, status_code: int, message: str, response: requests.Response):
        super().__init__(f"CruxPass API error {status_code}: {message}")
        self.status_code = status_code
        self.response = response


class CruxPass:
    """Small requests-based client for CruxPass publisher APIs."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://cruxpass.com",
        timeout: float = 10.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    def create_group(self, *, name: str, slug: str) -> dict[str, Any]:
        return self._request("POST", "/api/groups/", json={"name": name, "slug": slug})

    def list_groups(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/groups/")

    def create_feed(
        self,
        *,
        name: str,
        slug: str,
        group: Optional[str] = None,
        color: str = "",
    ) -> dict[str, Any]:
        payload = {"name": name, "slug": slug, "group": group, "color": color}
        return self._request("POST", "/api/feeds/", json=payload)

    def list_feeds(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/feeds/")

    def list_subscribers(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/subscribers/")

    def create_subscriber(
        self,
        *,
        feeds: Sequence[str],
        label: str = "",
        email: str = "",
        calendar_name: str = "",
    ) -> dict[str, Any]:
        payload = {
            "label": label,
            "email": email,
            "calendar_name": calendar_name,
            "feeds": feeds,
        }
        return self._request("POST", "/api/subscribers/", json=payload)

    def upsert_event(
        self,
        *,
        feed_slug: str,
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
        payload = {
            "external_id": external_id,
            "summary": summary,
            "description": description,
            "location": location,
            "start": _serialize_temporal(start),
            "end": _serialize_temporal(end),
            "all_day": all_day,
            "status": status,
            "busy": busy,
        }
        return self._request(
            "POST", f"/api/feeds/{_quote_path_part(feed_slug)}/events/", json=payload
        )

    def cancel_event(
        self,
        *,
        feed_slug: str,
        external_id: str,
        summary: str,
        start: Temporal,
        end: Temporal,
        description: str = "",
        location: str = "",
        all_day: bool = False,
    ) -> dict[str, Any]:
        return self.upsert_event(
            feed_slug=feed_slug,
            external_id=external_id,
            summary=summary,
            start=start,
            end=end,
            description=description,
            location=location,
            all_day=all_day,
            status="cancelled",
            busy=False,
        )

    def upsert_recurring_schedule(
        self,
        *,
        feed_slug: str,
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
        count: Optional[int] = None,
        until: Optional[Temporal] = None,
        window_months: int = 6,
    ) -> dict[str, Any]:
        payload = {
            "external_id": external_id,
            "summary": summary,
            "description": description,
            "location": location,
            "first_start": _serialize_temporal(first_start),
            "first_end": _serialize_temporal(first_end),
            "all_day": all_day,
            "status": status,
            "busy": busy,
            "frequency": frequency,
            "interval": interval,
            "count": count,
            "until": _serialize_temporal(until) if until is not None else None,
            "window_months": window_months,
        }
        return self._request(
            "POST",
            f"/api/feeds/{_quote_path_part(feed_slug)}/recurring-schedules/",
            json=payload,
        )

    def upsert_recurring_exception(
        self,
        *,
        feed_slug: str,
        schedule_external_id: str,
        occurrence_number: int,
        action: str,
        start: Optional[Temporal] = None,
        end: Optional[Temporal] = None,
        summary: str = "",
        description: str = "",
        location: str = "",
    ) -> dict[str, Any]:
        payload = {
            "occurrence_number": occurrence_number,
            "action": action,
            "start": _serialize_temporal(start) if start is not None else None,
            "end": _serialize_temporal(end) if end is not None else None,
            "summary": summary,
            "description": description,
            "location": location,
        }
        return self._request(
            "POST",
            (
                f"/api/feeds/{_quote_path_part(feed_slug)}/recurring-schedules/"
                f"{_quote_path_part(schedule_external_id)}/exceptions/"
            ),
            json=payload,
        )

    def move_recurring_occurrence(
        self,
        *,
        feed_slug: str,
        schedule_external_id: str,
        occurrence_number: int,
        start: Temporal,
        end: Temporal,
        summary: str = "",
        description: str = "",
        location: str = "",
    ) -> dict[str, Any]:
        return self.upsert_recurring_exception(
            feed_slug=feed_slug,
            schedule_external_id=schedule_external_id,
            occurrence_number=occurrence_number,
            action="moved",
            start=start,
            end=end,
            summary=summary,
            description=description,
            location=location,
        )

    def skip_recurring_occurrence(
        self,
        *,
        feed_slug: str,
        schedule_external_id: str,
        occurrence_number: int,
    ) -> dict[str, Any]:
        return self.upsert_recurring_exception(
            feed_slug=feed_slug,
            schedule_external_id=schedule_external_id,
            occurrence_number=occurrence_number,
            action="skipped",
        )

    def cancel_recurring_occurrence(
        self,
        *,
        feed_slug: str,
        schedule_external_id: str,
        occurrence_number: int,
    ) -> dict[str, Any]:
        return self.upsert_recurring_exception(
            feed_slug=feed_slug,
            schedule_external_id=schedule_external_id,
            occurrence_number=occurrence_number,
            action="cancelled",
        )

    def get_subscriber_feed_ics(self, token: str) -> str:
        response = self.session.request(
            "GET",
            f"{self.base_url}/f/{_quote_path_part(token)}.ics",
            headers={"Accept": "text/calendar"},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise APIError(response.status_code, _response_message(response), response)
        return response.text

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Mapping[str, Any]] = None,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        """Make an authenticated JSON request to a CruxPass API path."""
        if not path.startswith("/"):
            path = f"/{path}"
        request_kwargs: dict[str, Any] = {
            "headers": {
                "Authorization": f"Api-Key {self.api_key}",
                "Accept": "application/json",
            },
            "timeout": self.timeout,
        }
        if json is not None:
            request_kwargs["json"] = json
        if params is not None:
            request_kwargs["params"] = params

        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            **request_kwargs,
        )
        if response.status_code >= 400:
            raise APIError(response.status_code, _response_message(response), response)
        if response.status_code == 204:
            return None
        return response.json()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        return self.request(method, path, json=json)


def _serialize_temporal(value: Temporal) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        serialized = value.isoformat()
        if value.tzinfo == timezone.utc:
            return serialized.replace("+00:00", "Z")
        return serialized
    return value.isoformat()


def _quote_path_part(value: str) -> str:
    return quote(value, safe="")


def _response_message(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, str):
            return detail
    return str(data)
