from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping, Optional

import requests


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

    def create_subscriber(
        self,
        *,
        feeds: list[str],
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
        start: date | datetime | str,
        end: date | datetime | str,
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
        return self._request("POST", f"/api/feeds/{feed_slug}/events/", json=payload)

    def cancel_event(
        self,
        *,
        feed_slug: str,
        external_id: str,
        summary: str,
        start: date | datetime | str,
        end: date | datetime | str,
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

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            headers={
                "Authorization": f"Api-Key {self.api_key}",
                "Accept": "application/json",
            },
            json=json,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise APIError(response.status_code, _response_message(response), response)
        if response.status_code == 204:
            return None
        return response.json()


def _serialize_temporal(value: date | datetime | str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        serialized = value.isoformat()
        if value.tzinfo == timezone.utc:
            return serialized.replace("+00:00", "Z")
        return serialized
    return value.isoformat()


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
