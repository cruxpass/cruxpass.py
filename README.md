# cruxpass

Python client for the CruxPass API.

This package is intentionally small while the public API settles. It provides a
thin wrapper around CruxPass publisher endpoints for creating feeds,
subscribers, and idempotently pushing calendar events.

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

## Status

Placeholder release. The surface area may change before `1.0`.
