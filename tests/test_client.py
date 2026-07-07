import json
import os
from datetime import UTC, datetime
from unittest import IsolatedAsyncioTestCase, TestCase, mock

import httpx

from cruxpass import (
    APIError,
    AsyncCruxPass,
    AuthenticationError,
    CruxPass,
    FeedResponse,
    NotFoundError,
    RateLimitError,
    ServerError,
)


class ScriptedTransport(httpx.MockTransport):
    """Mock transport that records requests and replays scripted responses.

    Each script entry is an httpx.Response or an exception to raise. The last
    entry repeats once the script is exhausted.
    """

    def __init__(self, *script):
        self.script = list(script)
        self.requests = []
        super().__init__(self._handle)

    def _handle(self, request):
        self.requests.append(request)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item


def sync_client(*script, **kwargs) -> tuple[CruxPass, ScriptedTransport]:
    transport = ScriptedTransport(*script)
    client = CruxPass(
        kwargs.pop("api_key", "pk_test"),
        http_client=httpx.Client(transport=transport),
        **kwargs,
    )
    return client, transport


def async_client(*script, **kwargs) -> tuple[AsyncCruxPass, ScriptedTransport]:
    transport = ScriptedTransport(*script)
    client = AsyncCruxPass(
        kwargs.pop("api_key", "pk_test"),
        http_client=httpx.AsyncClient(transport=transport),
        **kwargs,
    )
    return client, transport


def body_of(request: httpx.Request) -> dict:
    return json.loads(request.content)


class ClientTests(TestCase):
    def test_upsert_event_sends_auth_header_and_payload(self):
        client, transport = sync_client(
            httpx.Response(200, json={"external_id": "event-1"})
        )

        result = client.upsert_event(
            feed_slug="events",
            external_id="event-1",
            summary="Demo Event",
            start=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
            end=datetime(2026, 7, 21, 0, 30, tzinfo=UTC),
        )

        self.assertEqual(result, {"external_id": "event-1"})
        request = transport.requests[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(
            str(request.url), "https://cruxpass.com/api/feeds/events/events/"
        )
        self.assertEqual(request.headers["Authorization"], "Api-Key pk_test")
        self.assertTrue(request.headers["User-Agent"].startswith("cruxpass-python/"))
        payload = body_of(request)
        self.assertEqual(payload["start"], "2026-07-20T23:00:00Z")
        self.assertEqual(payload["status"], "confirmed")

    def test_error_responses_map_to_typed_exceptions(self):
        cases = [
            (400, APIError),
            (401, AuthenticationError),
            (403, AuthenticationError),
            (404, NotFoundError),
        ]
        for status, exception_type in cases:
            with self.subTest(status=status):
                client, _ = sync_client(httpx.Response(status, json={"detail": "Nope"}))
                with self.assertRaises(exception_type) as ctx:
                    client.list_feeds()
                self.assertEqual(ctx.exception.status_code, status)
                self.assertIn("Nope", str(ctx.exception))

    def test_rate_limit_and_server_errors_raise_after_retries(self):
        cases = [(429, RateLimitError), (503, ServerError)]
        for status, exception_type in cases:
            with self.subTest(status=status):
                client, transport = sync_client(
                    httpx.Response(status, json={"detail": "Busy"}),
                    max_retries=1,
                )
                with (
                    mock.patch("cruxpass._client.time.sleep") as sleep,
                    self.assertRaises(exception_type),
                ):
                    client.list_feeds()
                self.assertEqual(len(transport.requests), 2)
                self.assertEqual(sleep.call_count, 1)

    def test_retry_recovers_after_transient_server_error(self):
        client, transport = sync_client(
            httpx.Response(503, json={"detail": "Busy"}),
            httpx.Response(200, json=[{"slug": "events"}]),
        )

        with mock.patch("cruxpass._client.time.sleep") as sleep:
            result = client.list_feeds()

        self.assertEqual(result, [{"slug": "events"}])
        self.assertEqual(len(transport.requests), 2)
        sleep.assert_called_once_with(0.5)

    def test_list_helpers_follow_paginated_envelopes(self):
        client, transport = sync_client(
            httpx.Response(
                200,
                json={
                    "count": 2,
                    "next": "https://cruxpass.com/api/feeds/?page=2&page_size=100",
                    "previous": None,
                    "results": [{"slug": "events"}],
                },
            ),
            httpx.Response(
                200,
                json={
                    "count": 2,
                    "next": None,
                    "previous": "https://cruxpass.com/api/feeds/",
                    "results": [{"slug": "classes"}],
                },
            ),
        )

        result = client.list_feeds()

        self.assertEqual(result, [{"slug": "events"}, {"slug": "classes"}])
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(
            str(transport.requests[0].url), "https://cruxpass.com/api/feeds/"
        )
        self.assertEqual(
            str(transport.requests[1].url),
            "https://cruxpass.com/api/feeds/?page=2&page_size=100",
        )

    def test_list_events_targets_feed_events_endpoint(self):
        client, transport = sync_client(
            httpx.Response(
                200,
                json={
                    "count": 1,
                    "next": None,
                    "previous": None,
                    "results": [{"external_id": "event-1"}],
                },
            )
        )

        result = client.list_events(feed_slug="events/2026")

        self.assertEqual(result, [{"external_id": "event-1"}])
        self.assertEqual(
            str(transport.requests[0].url),
            "https://cruxpass.com/api/feeds/events%2F2026/events/",
        )

    def test_lifecycle_helpers_target_detail_endpoints(self):
        client, transport = sync_client(
            httpx.Response(200, json={"slug": "outpost"}),
            httpx.Response(200, json={"slug": "outpost", "name": "Updated"}),
            httpx.Response(204),
            httpx.Response(200, json={"slug": "events"}),
            httpx.Response(200, json={"slug": "events", "group": None}),
            httpx.Response(204),
            httpx.Response(200, json={"token": "sub_123"}),
            httpx.Response(200, json={"token": "sub_123", "feeds": ["events"]}),
        )

        self.assertEqual(client.get_group("outpost"), {"slug": "outpost"})
        self.assertEqual(
            client.update_group("outpost", name="Updated")["name"], "Updated"
        )
        self.assertIsNone(client.delete_group("outpost"))
        self.assertEqual(client.get_feed("events"), {"slug": "events"})
        self.assertIsNone(
            client.update_feed("events", name="Events", clear_group=True)["group"]
        )
        self.assertIsNone(client.delete_feed("events"))
        self.assertEqual(client.get_subscriber("sub/123"), {"token": "sub_123"})
        self.assertEqual(
            client.update_subscriber(
                "sub/123",
                label="Household",
                email="household@example.com",
                calendar_name="Calendar",
                feeds=["events"],
            )["feeds"],
            ["events"],
        )

        urls = [str(request.url) for request in transport.requests]
        self.assertEqual(
            urls,
            [
                "https://cruxpass.com/api/groups/outpost/",
                "https://cruxpass.com/api/groups/outpost/",
                "https://cruxpass.com/api/groups/outpost/",
                "https://cruxpass.com/api/feeds/events/",
                "https://cruxpass.com/api/feeds/events/",
                "https://cruxpass.com/api/feeds/events/",
                "https://cruxpass.com/api/subscribers/sub%2F123/",
                "https://cruxpass.com/api/subscribers/sub%2F123/",
            ],
        )
        self.assertEqual(transport.requests[2].method, "DELETE")
        self.assertEqual(transport.requests[4].method, "PATCH")
        self.assertEqual(
            body_of(transport.requests[4]), {"name": "Events", "group": None}
        )
        self.assertEqual(
            body_of(transport.requests[7]),
            {
                "label": "Household",
                "email": "household@example.com",
                "calendar_name": "Calendar",
                "feeds": ["events"],
            },
        )

    def test_update_feed_rejects_conflicting_group_arguments(self):
        client, _ = sync_client(httpx.Response(200, json={}))

        with self.assertRaises(ValueError):
            client.update_feed("events", group="outpost", clear_group=True)

    def test_retry_honors_retry_after_header(self):
        client, _ = sync_client(
            httpx.Response(429, headers={"Retry-After": "3"}, json={}),
            httpx.Response(200, json=[]),
        )

        with mock.patch("cruxpass._client.time.sleep") as sleep:
            client.list_feeds()

        sleep.assert_called_once_with(3.0)

    def test_retry_recovers_after_connect_error(self):
        client, transport = sync_client(
            httpx.ConnectError("boom"),
            httpx.Response(200, json=[]),
        )

        with mock.patch("cruxpass._client.time.sleep"):
            result = client.list_feeds()

        self.assertEqual(result, [])
        self.assertEqual(len(transport.requests), 2)

    def test_connect_error_raises_when_retries_exhausted(self):
        client, transport = sync_client(httpx.ConnectError("boom"), max_retries=1)

        with (
            mock.patch("cruxpass._client.time.sleep"),
            self.assertRaises(httpx.ConnectError),
        ):
            client.list_feeds()

        self.assertEqual(len(transport.requests), 2)

    def test_api_key_is_required(self):
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            self.assertRaises(ValueError),
        ):
            CruxPass()

    def test_api_key_and_base_url_fall_back_to_environment(self):
        env = {
            "CRUXPASS_API_KEY": "pk_env",
            "CRUXPASS_BASE_URL": "https://staging.cruxpass.com/",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            transport = ScriptedTransport(httpx.Response(200, json=[]))
            client = CruxPass(http_client=httpx.Client(transport=transport))
            client.list_feeds()

        request = transport.requests[0]
        self.assertEqual(str(request.url), "https://staging.cruxpass.com/api/feeds/")
        self.assertEqual(request.headers["Authorization"], "Api-Key pk_env")

    def test_context_manager_usage(self):
        client, _ = sync_client(httpx.Response(200, json=[]))
        with client as managed:
            self.assertEqual(managed.list_feeds(), [])

    def test_get_project_uses_current_project_endpoint(self):
        client, transport = sync_client(
            httpx.Response(
                200,
                json={"id": 1, "name": "Project A", "slug": "project-a"},
            )
        )

        result = client.get_project()

        self.assertEqual(result["slug"], "project-a")
        request = transport.requests[0]
        self.assertEqual(request.method, "GET")
        self.assertEqual(str(request.url), "https://cruxpass.com/api/project/")

    def test_update_project_sends_feed_domain_payload(self):
        client, transport = sync_client(
            httpx.Response(
                200, json={"slug": "project-a", "feed_domain": "feeds.example.com"}
            )
        )

        result = client.update_project(feed_domain="https://feeds.example.com/")

        self.assertEqual(result["feed_domain"], "feeds.example.com")
        request = transport.requests[0]
        self.assertEqual(request.method, "PATCH")
        self.assertEqual(str(request.url), "https://cruxpass.com/api/project/")
        self.assertEqual(
            body_of(request), {"feed_domain": "https://feeds.example.com/"}
        )

    def test_list_subscribers_uses_publisher_endpoint(self):
        client, transport = sync_client(
            httpx.Response(200, json=[{"token": "sub_123"}])
        )

        result = client.list_subscribers()

        self.assertEqual(result, [{"token": "sub_123"}])
        self.assertEqual(
            str(transport.requests[0].url), "https://cruxpass.com/api/subscribers/"
        )

    def test_subscriber_lifecycle_helpers_target_token_actions(self):
        client, transport = sync_client(
            httpx.Response(200, json={"token": "new-token"})
        )

        client.rotate_subscriber_token("old/token")
        client.deactivate_subscriber("new-token")
        client.refresh_subscriber_artifact("new-token")

        urls = [str(request.url) for request in transport.requests]
        self.assertEqual(
            urls,
            [
                "https://cruxpass.com/api/subscribers/old%2Ftoken/rotate-token/",
                "https://cruxpass.com/api/subscribers/new-token/deactivate/",
                "https://cruxpass.com/api/subscribers/new-token/refresh-artifact/",
            ],
        )
        for request in transport.requests:
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.headers["Authorization"], "Api-Key pk_test")

    def test_upsert_recurring_schedule_sends_full_schedule_payload(self):
        client, transport = sync_client(
            httpx.Response(200, json={"schedule": {"external_id": "weekly-meeting"}})
        )

        result = client.upsert_recurring_schedule(
            feed_slug="events",
            external_id="weekly-meeting",
            summary="Weekly Meeting",
            first_start=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
            first_end=datetime(2026, 7, 21, 0, 30, tzinfo=UTC),
            frequency="weekly",
            timezone="America/Denver",
            count=3,
        )

        self.assertEqual(result, {"schedule": {"external_id": "weekly-meeting"}})
        request = transport.requests[0]
        self.assertEqual(
            str(request.url),
            "https://cruxpass.com/api/feeds/events/recurring-schedules/",
        )
        payload = body_of(request)
        self.assertEqual(payload["first_start"], "2026-07-20T23:00:00Z")
        self.assertEqual(payload["first_end"], "2026-07-21T00:30:00Z")
        self.assertEqual(payload["frequency"], "weekly")
        self.assertEqual(payload["timezone"], "America/Denver")
        self.assertEqual(payload["interval"], 1)
        self.assertEqual(payload["count"], 3)
        self.assertIsNone(payload["until"])

    def test_recurring_exception_helpers_target_occurrence_endpoint(self):
        client, transport = sync_client(
            httpx.Response(200, json={"exception": {"occurrence_number": 2}})
        )

        result = client.move_recurring_occurrence(
            feed_slug="events",
            schedule_external_id="weekly-meeting",
            occurrence_number=2,
            start=datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
            end=datetime(2026, 7, 28, 2, 0, tzinfo=UTC),
            summary="Moved Weekly Meeting",
        )

        self.assertEqual(result, {"exception": {"occurrence_number": 2}})
        request = transport.requests[0]
        self.assertEqual(
            str(request.url),
            "https://cruxpass.com/api/feeds/events/recurring-schedules/"
            "weekly-meeting/exceptions/",
        )
        payload = body_of(request)
        self.assertEqual(payload["occurrence_number"], 2)
        self.assertEqual(payload["action"], "moved")
        self.assertEqual(payload["start"], "2026-07-28T01:00:00Z")
        self.assertEqual(payload["end"], "2026-07-28T02:00:00Z")
        self.assertEqual(payload["summary"], "Moved Weekly Meeting")

    def test_get_subscriber_feed_ics_fetches_public_feed_without_auth(self):
        client, transport = sync_client(
            httpx.Response(200, text="BEGIN:VCALENDAR\nEND:VCALENDAR\n")
        )

        result = client.get_subscriber_feed_ics("feed-token")

        self.assertEqual(result, "BEGIN:VCALENDAR\nEND:VCALENDAR\n")
        request = transport.requests[0]
        self.assertEqual(str(request.url), "https://cruxpass.com/f/feed-token.ics")
        self.assertEqual(request.headers["Accept"], "text/calendar")
        self.assertNotIn("Authorization", request.headers)

    def test_get_subscriber_feed_returns_cache_metadata(self):
        client, _ = sync_client(
            httpx.Response(
                200,
                text="BEGIN:VCALENDAR\nEND:VCALENDAR\n",
                headers={
                    "ETag": '"abc123"',
                    "Last-Modified": "Tue, 07 Jul 2026 12:00:00 GMT",
                    "Content-Type": "text/calendar",
                },
            )
        )

        result = client.get_subscriber_feed("feed-token")

        self.assertIsInstance(result, FeedResponse)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.text, "BEGIN:VCALENDAR\nEND:VCALENDAR\n")
        self.assertEqual(result.etag, '"abc123"')
        self.assertEqual(result.last_modified, "Tue, 07 Jul 2026 12:00:00 GMT")

    def test_get_subscriber_feed_can_make_conditional_request(self):
        client, transport = sync_client(
            httpx.Response(304, headers={"ETag": '"abc123"'})
        )

        result = client.get_subscriber_feed(
            "feed-token",
            etag='"abc123"',
            modified_since="Tue, 07 Jul 2026 12:00:00 GMT",
        )

        self.assertEqual(result.status_code, 304)
        self.assertEqual(result.text, "")
        self.assertEqual(result.etag, '"abc123"')
        request = transport.requests[0]
        self.assertEqual(request.headers["If-None-Match"], '"abc123"')
        self.assertEqual(
            request.headers["If-Modified-Since"], "Tue, 07 Jul 2026 12:00:00 GMT"
        )

    def test_request_returns_none_for_no_content(self):
        client, _ = sync_client(httpx.Response(204))

        self.assertIsNone(client.request("DELETE", "/api/feeds/old/"))

    def test_request_normalizes_relative_paths(self):
        client, transport = sync_client(httpx.Response(200, json=[]))

        client.request("GET", "api/feeds/", params={"page": 2})

        self.assertEqual(
            str(transport.requests[0].url), "https://cruxpass.com/api/feeds/?page=2"
        )


class AsyncClientTests(IsolatedAsyncioTestCase):
    async def test_upsert_event_sends_auth_header_and_payload(self):
        client, transport = async_client(
            httpx.Response(200, json={"external_id": "event-1"})
        )

        async with client:
            result = await client.upsert_event(
                feed_slug="events",
                external_id="event-1",
                summary="Demo Event",
                start=datetime(2026, 7, 20, 23, 0, tzinfo=UTC),
                end=datetime(2026, 7, 21, 0, 30, tzinfo=UTC),
            )

        self.assertEqual(result, {"external_id": "event-1"})
        request = transport.requests[0]
        self.assertEqual(
            str(request.url), "https://cruxpass.com/api/feeds/events/events/"
        )
        self.assertEqual(request.headers["Authorization"], "Api-Key pk_test")
        self.assertEqual(body_of(request)["start"], "2026-07-20T23:00:00Z")

    async def test_error_responses_map_to_typed_exceptions(self):
        client, _ = async_client(httpx.Response(401, json={"detail": "Nope"}))

        async with client:
            with self.assertRaises(AuthenticationError) as ctx:
                await client.list_feeds()

        self.assertEqual(ctx.exception.status_code, 401)

    async def test_retry_recovers_after_transient_server_error(self):
        client, transport = async_client(
            httpx.Response(503, json={"detail": "Busy"}),
            httpx.Response(200, json=[]),
        )

        with mock.patch(
            "cruxpass._async_client.asyncio.sleep", new_callable=mock.AsyncMock
        ) as sleep:
            async with client:
                result = await client.list_feeds()

        self.assertEqual(result, [])
        self.assertEqual(len(transport.requests), 2)
        sleep.assert_awaited_once_with(0.5)

    async def test_list_helpers_follow_paginated_envelopes(self):
        client, transport = async_client(
            httpx.Response(
                200,
                json={
                    "count": 2,
                    "next": "https://cruxpass.com/api/groups/?page=2",
                    "previous": None,
                    "results": [{"slug": "primary"}],
                },
            ),
            httpx.Response(
                200,
                json={
                    "count": 2,
                    "next": None,
                    "previous": "https://cruxpass.com/api/groups/",
                    "results": [{"slug": "secondary"}],
                },
            ),
        )

        async with client:
            result = await client.list_groups()

        self.assertEqual(result, [{"slug": "primary"}, {"slug": "secondary"}])
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(
            str(transport.requests[1].url), "https://cruxpass.com/api/groups/?page=2"
        )

    async def test_list_events_targets_feed_events_endpoint(self):
        client, transport = async_client(
            httpx.Response(
                200,
                json={
                    "count": 1,
                    "next": None,
                    "previous": None,
                    "results": [{"external_id": "event-1"}],
                },
            )
        )

        async with client:
            result = await client.list_events(feed_slug="events")

        self.assertEqual(result, [{"external_id": "event-1"}])
        self.assertEqual(
            str(transport.requests[0].url),
            "https://cruxpass.com/api/feeds/events/events/",
        )

    async def test_lifecycle_helpers_target_detail_endpoints(self):
        client, transport = async_client(
            httpx.Response(200, json={"slug": "events"}),
            httpx.Response(200, json={"slug": "events", "name": "Updated"}),
            httpx.Response(204),
            httpx.Response(200, json={"token": "sub_123", "feeds": ["events"]}),
        )

        async with client:
            self.assertEqual(await client.get_feed("events"), {"slug": "events"})
            self.assertEqual(
                (await client.update_feed("events", name="Updated"))["name"],
                "Updated",
            )
            self.assertIsNone(await client.delete_feed("events"))
            self.assertEqual(
                (await client.update_subscriber("sub_123", feeds=["events"]))["feeds"],
                ["events"],
            )

        self.assertEqual(
            [request.method for request in transport.requests],
            ["GET", "PATCH", "DELETE", "PATCH"],
        )
        self.assertEqual(
            str(transport.requests[3].url),
            "https://cruxpass.com/api/subscribers/sub_123/",
        )

    async def test_get_subscriber_feed_can_make_conditional_request(self):
        client, transport = async_client(
            httpx.Response(304, headers={"ETag": '"abc123"'})
        )

        async with client:
            result = await client.get_subscriber_feed("feed-token", etag='"abc123"')

        self.assertEqual(result.status_code, 304)
        self.assertEqual(transport.requests[0].headers["If-None-Match"], '"abc123"')
