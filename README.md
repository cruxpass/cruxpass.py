# cruxpass

Python client for the CruxPass API.

This package is intentionally small while the public API settles. It provides a
thin `requests`-based wrapper around CruxPass publisher endpoints for creating
groups, feeds, subscribers, one-off events, and recurring schedules.

## Install

```bash
pip install cruxpass
```

## Usage

```python
from cruxpass import CruxPass

client = CruxPass(api_key="pk_...")

client.create_feed(name="Events", slug="events")

client.upsert_event(
    feed_slug="events",
    external_id="event-123",
    summary="Demo Event",
    start="2026-07-20T23:00:00Z",
    end="2026-07-21T00:30:00Z",
)

subscriber = client.create_subscriber(
    label="Demo subscriber",
    feeds=["events"],
)

print(subscriber["subscribe_url"])
```

## Recurring schedules

```python
client.upsert_recurring_schedule(
    feed_slug="events",
    external_id="weekly-meeting",
    summary="Weekly Meeting",
    first_start="2026-07-20T23:00:00Z",
    first_end="2026-07-21T00:00:00Z",
    frequency="weekly",
    count=12,
)

client.move_recurring_occurrence(
    feed_slug="events",
    schedule_external_id="weekly-meeting",
    occurrence_number=2,
    start="2026-07-28T01:00:00Z",
    end="2026-07-28T02:00:00Z",
)

client.cancel_recurring_occurrence(
    feed_slug="events",
    schedule_external_id="weekly-meeting",
    occurrence_number=3,
)
```

## Helpers

The client exposes the documented REST surface:

- `list_groups()` / `create_group(...)`
- `list_feeds()` / `create_feed(...)`
- `list_subscribers()` / `create_subscriber(...)`
- `upsert_event(...)` / `cancel_event(...)`
- `upsert_recurring_schedule(...)`
- `upsert_recurring_exception(...)`
- `move_recurring_occurrence(...)`
- `skip_recurring_occurrence(...)`
- `cancel_recurring_occurrence(...)`
- `get_subscriber_feed_ics(token)`

For API paths that do not have a named helper yet, use `client.request(method,
path, json=..., params=...)`.

## Status

Placeholder release. The surface area may change before `1.0`.
