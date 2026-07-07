from datetime import datetime, timezone
from unittest import TestCase

from cruxpass import APIError, CruxPass


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.text = str(self._body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


class ClientTests(TestCase):
    def test_upsert_event_sends_auth_header_and_payload(self):
        session = FakeSession(FakeResponse(body={"external_id": "event-1"}))
        client = CruxPass(
            "pk_test",
            timeout=3,
            session=session,
        )

        result = client.upsert_event(
            feed_slug="events",
            external_id="event-1",
            summary="Demo Event",
            start=datetime(2026, 7, 20, 23, 0, tzinfo=timezone.utc),
            end=datetime(2026, 7, 21, 0, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(result, {"external_id": "event-1"})
        args, kwargs = session.calls[0]
        self.assertEqual(args, ("POST", "https://cruxpass.com/api/feeds/events/events/"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Api-Key pk_test")
        self.assertEqual(kwargs["timeout"], 3)
        self.assertEqual(kwargs["json"]["start"], "2026-07-20T23:00:00Z")
        self.assertEqual(kwargs["json"]["status"], "confirmed")

    def test_error_response_raises_api_error(self):
        session = FakeSession(FakeResponse(status_code=401, body={"detail": "Nope"}))
        client = CruxPass("pk_test", session=session)

        with self.assertRaises(APIError) as ctx:
            client.list_feeds()

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Nope", str(ctx.exception))
