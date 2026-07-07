"""Synchronous CruxPass client."""

import time
from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import Any, Self

import httpx

from . import _core
from ._core import FeedResponse, Temporal
from ._version import __version__


class CruxPass:
    """httpx-based client for CruxPass publisher APIs."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float | httpx.Timeout = _core.DEFAULT_TIMEOUT,
        max_retries: int = _core.DEFAULT_MAX_RETRIES,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = _core.resolve_api_key(api_key)
        self.base_url = _core.resolve_base_url(base_url)
        self.max_retries = max_retries
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._owns_client:
            self.close()

    def get_project(self) -> dict[str, Any]:
        return self._request("GET", "/api/project/")

    def update_project(self, *, feed_domain: str) -> dict[str, Any]:
        return self._request(
            "PATCH", "/api/project/", json={"feed_domain": feed_domain}
        )

    def create_group(self, *, name: str, slug: str) -> dict[str, Any]:
        return self._request("POST", "/api/groups/", json={"name": name, "slug": slug})

    def list_groups(self) -> list[dict[str, Any]]:
        return self._list_all("/api/groups/")

    def get_group(self, slug: str) -> dict[str, Any]:
        return self._request("GET", f"/api/groups/{_core.quote_path_part(slug)}/")

    def update_group(self, slug: str, *, name: str | None = None) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/api/groups/{_core.quote_path_part(slug)}/",
            json=_core.update_payload(name=name),
        )

    def delete_group(self, slug: str) -> None:
        self._request("DELETE", f"/api/groups/{_core.quote_path_part(slug)}/")

    def create_feed(
        self,
        *,
        name: str,
        slug: str,
        group: str | None = None,
        color: str = "",
    ) -> dict[str, Any]:
        payload = {"name": name, "slug": slug, "group": group, "color": color}
        return self._request("POST", "/api/feeds/", json=payload)

    def list_feeds(self) -> list[dict[str, Any]]:
        return self._list_all("/api/feeds/")

    def get_feed(self, slug: str) -> dict[str, Any]:
        return self._request("GET", f"/api/feeds/{_core.quote_path_part(slug)}/")

    def update_feed(
        self,
        slug: str,
        *,
        name: str | None = None,
        group: str | None = None,
        color: str | None = None,
        clear_group: bool = False,
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/api/feeds/{_core.quote_path_part(slug)}/",
            json=_core.feed_update_payload(
                name=name, group=group, color=color, clear_group=clear_group
            ),
        )

    def delete_feed(self, slug: str) -> None:
        self._request("DELETE", f"/api/feeds/{_core.quote_path_part(slug)}/")

    def list_subscribers(self) -> list[dict[str, Any]]:
        return self._list_all("/api/subscribers/")

    def get_subscriber(self, token: str) -> dict[str, Any]:
        return self._request("GET", f"/api/subscribers/{_core.quote_path_part(token)}/")

    def update_subscriber(
        self,
        token: str,
        *,
        label: str | None = None,
        email: str | None = None,
        calendar_name: str | None = None,
        feeds: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/api/subscribers/{_core.quote_path_part(token)}/",
            json=_core.subscriber_update_payload(
                label=label,
                email=email,
                calendar_name=calendar_name,
                feeds=feeds,
            ),
        )

    def create_subscriber(
        self,
        *,
        feeds: Sequence[str],
        label: str = "",
        email: str = "",
        calendar_name: str = "",
    ) -> dict[str, Any]:
        payload = _core.subscriber_payload(
            feeds=feeds, label=label, email=email, calendar_name=calendar_name
        )
        return self._request("POST", "/api/subscribers/", json=payload)

    def deactivate_subscriber(self, token: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/subscribers/{_core.quote_path_part(token)}/deactivate/",
        )

    def rotate_subscriber_token(self, token: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/subscribers/{_core.quote_path_part(token)}/rotate-token/",
        )

    def refresh_subscriber_artifact(self, token: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/subscribers/{_core.quote_path_part(token)}/refresh-artifact/",
        )

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
        payload = _core.event_payload(
            external_id=external_id,
            summary=summary,
            start=start,
            end=end,
            description=description,
            location=location,
            all_day=all_day,
            status=status,
            busy=busy,
        )
        return self._request(
            "POST",
            f"/api/feeds/{_core.quote_path_part(feed_slug)}/events/",
            json=payload,
        )

    def list_events(self, *, feed_slug: str) -> list[dict[str, Any]]:
        return self._list_all(f"/api/feeds/{_core.quote_path_part(feed_slug)}/events/")

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
        timezone: str = "",
        interval: int = 1,
        count: int | None = None,
        until: Temporal | None = None,
        window_months: int = 6,
    ) -> dict[str, Any]:
        payload = _core.schedule_payload(
            external_id=external_id,
            summary=summary,
            first_start=first_start,
            first_end=first_end,
            frequency=frequency,
            description=description,
            location=location,
            all_day=all_day,
            status=status,
            busy=busy,
            timezone=timezone,
            interval=interval,
            count=count,
            until=until,
            window_months=window_months,
        )
        return self._request(
            "POST",
            f"/api/feeds/{_core.quote_path_part(feed_slug)}/recurring-schedules/",
            json=payload,
        )

    def upsert_recurring_exception(
        self,
        *,
        feed_slug: str,
        schedule_external_id: str,
        occurrence_number: int,
        action: str,
        start: Temporal | None = None,
        end: Temporal | None = None,
        summary: str = "",
        description: str = "",
        location: str = "",
    ) -> dict[str, Any]:
        payload = _core.exception_payload(
            occurrence_number=occurrence_number,
            action=action,
            start=start,
            end=end,
            summary=summary,
            description=description,
            location=location,
        )
        return self._request(
            "POST",
            (
                f"/api/feeds/{_core.quote_path_part(feed_slug)}/recurring-schedules/"
                f"{_core.quote_path_part(schedule_external_id)}/exceptions/"
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

    def get_subscriber_feed(
        self,
        token: str,
        *,
        etag: str | None = None,
        modified_since: str | None = None,
    ) -> FeedResponse:
        response = self._send(
            "GET",
            f"{self.base_url}{_core.feed_path(token)}",
            headers=_core.feed_headers(etag, modified_since),
        )
        if response.status_code >= 400:
            raise _core.error_for_response(response)
        return _core.feed_response(response)

    def get_subscriber_feed_ics(self, token: str) -> str:
        return self.get_subscriber_feed(token).text

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        """Make an authenticated JSON request to a CruxPass API path."""
        response = self._send(
            method,
            f"{self.base_url}{_core.normalize_path(path)}",
            headers=self._auth_headers(),
            json=json,
            params=params,
        )
        if response.status_code >= 400:
            raise _core.error_for_response(response)
        return _core.json_body(response)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        return self.request(method, path, json=json, params=params)

    def _list_all(self, path: str) -> list[dict[str, Any]]:
        params: Mapping[str, Any] | None = None
        items: list[dict[str, Any]] = []
        while True:
            page, next_url = _core.list_response_page(
                self._request("GET", path, params=params)
            )
            items.extend(page)
            if next_url is None:
                return items
            params = _core.params_from_next_url(next_url)

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Api-Key {self.api_key}",
            "Accept": "application/json",
            "User-Agent": f"cruxpass-python/{__version__}",
        }

    def _send(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        kwargs: dict[str, Any] = {"headers": headers}
        if json is not None:
            kwargs["json"] = json
        if params is not None:
            kwargs["params"] = params

        attempt = 0
        while True:
            try:
                response = self._client.request(method, url, **kwargs)
            except _core.RETRYABLE_EXCEPTIONS:
                if attempt >= self.max_retries:
                    raise
                time.sleep(_core.retry_delay(attempt, None))
            else:
                if (
                    response.status_code not in _core.RETRYABLE_STATUS_CODES
                    or attempt >= self.max_retries
                ):
                    return response
                time.sleep(
                    _core.retry_delay(attempt, response.headers.get("Retry-After"))
                )
            attempt += 1
