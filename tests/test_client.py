from datetime import datetime, timezone
from unittest import TestCase

from cruxpass import APIError, CruxPass


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=None):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.text = text if text is not None else str(self._body)

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

    def test_list_subscribers_uses_publisher_endpoint(self):
        session = FakeSession(FakeResponse(body=[{"token": "sub_123"}]))
        client = CruxPass("pk_test", session=session)

        result = client.list_subscribers()

        self.assertEqual(result, [{"token": "sub_123"}])
        args, kwargs = session.calls[0]
        self.assertEqual(args, ("GET", "https://cruxpass.com/api/subscribers/"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Api-Key pk_test")

    def test_upsert_recurring_schedule_sends_full_schedule_payload(self):
        session = FakeSession(
            FakeResponse(body={"schedule": {"external_id": "weekly-meeting"}})
        )
        client = CruxPass("pk_test", session=session)

        result = client.upsert_recurring_schedule(
            feed_slug="events",
            external_id="weekly-meeting",
            summary="Weekly Meeting",
            first_start=datetime(2026, 7, 20, 23, 0, tzinfo=timezone.utc),
            first_end=datetime(2026, 7, 21, 0, 30, tzinfo=timezone.utc),
            frequency="weekly",
            count=3,
        )

        self.assertEqual(result, {"schedule": {"external_id": "weekly-meeting"}})
        args, kwargs = session.calls[0]
        self.assertEqual(
            args,
            (
                "POST",
                "https://cruxpass.com/api/feeds/events/recurring-schedules/",
            ),
        )
        self.assertEqual(kwargs["json"]["first_start"], "2026-07-20T23:00:00Z")
        self.assertEqual(kwargs["json"]["first_end"], "2026-07-21T00:30:00Z")
        self.assertEqual(kwargs["json"]["frequency"], "weekly")
        self.assertEqual(kwargs["json"]["interval"], 1)
        self.assertEqual(kwargs["json"]["count"], 3)
        self.assertIsNone(kwargs["json"]["until"])

    def test_recurring_exception_helpers_target_occurrence_endpoint(self):
        session = FakeSession(
            FakeResponse(body={"exception": {"occurrence_number": 2}})
        )
        client = CruxPass("pk_test", session=session)

        result = client.move_recurring_occurrence(
            feed_slug="events",
            schedule_external_id="weekly-meeting",
            occurrence_number=2,
            start=datetime(2026, 7, 28, 1, 0, tzinfo=timezone.utc),
            end=datetime(2026, 7, 28, 2, 0, tzinfo=timezone.utc),
            summary="Moved Weekly Meeting",
        )

        self.assertEqual(result, {"exception": {"occurrence_number": 2}})
        args, kwargs = session.calls[0]
        self.assertEqual(
            args,
            (
                "POST",
                "https://cruxpass.com/api/feeds/events/recurring-schedules/"
                "weekly-meeting/exceptions/",
            ),
        )
        self.assertEqual(kwargs["json"]["occurrence_number"], 2)
        self.assertEqual(kwargs["json"]["action"], "moved")
        self.assertEqual(kwargs["json"]["start"], "2026-07-28T01:00:00Z")
        self.assertEqual(kwargs["json"]["end"], "2026-07-28T02:00:00Z")
        self.assertEqual(kwargs["json"]["summary"], "Moved Weekly Meeting")

    def test_get_subscriber_feed_ics_fetches_public_feed_without_auth(self):
        session = FakeSession(FakeResponse(text="BEGIN:VCALENDAR\nEND:VCALENDAR\n"))
        client = CruxPass("pk_test", timeout=5, session=session)

        result = client.get_subscriber_feed_ics("feed-token")

        self.assertEqual(result, "BEGIN:VCALENDAR\nEND:VCALENDAR\n")
        args, kwargs = session.calls[0]
        self.assertEqual(args, ("GET", "https://cruxpass.com/f/feed-token.ics"))
        self.assertEqual(kwargs["headers"], {"Accept": "text/calendar"})
        self.assertEqual(kwargs["timeout"], 5)
