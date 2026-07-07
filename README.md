# cruxpass

Python client for the [CruxPass](https://cruxpass.com) API.

CruxPass publishes subscribable, per-user calendar feeds on behalf of SaaS
platforms. This package is a nimble, fully typed client for the CruxPass
publisher REST surface: projects, groups, feeds, subscribers, one-off events,
recurring schedules, and public ICS feed reads.

- Python 3.13+
- Sync (`CruxPass`) and async (`AsyncCruxPass`) clients backed by `httpx`
- Automatic retries with backoff for connect errors, 429, and transient 5xx
  responses (safe because CruxPass writes are idempotent upserts keyed by
  `external_id`)
- Typed exceptions: `AuthenticationError`, `NotFoundError`, `RateLimitError`,
  `ServerError`, all subclasses of `APIError`
- `CRUXPASS_API_KEY` and `CRUXPASS_BASE_URL` environment fallbacks, matching
  the CruxPass server tooling

## Install

```bash
uv add cruxpass
# or
pip install cruxpass
```

## Usage

```python
from cruxpass import CruxPass

client = CruxPass(api_key="pk_...")  # or set CRUXPASS_API_KEY

client.update_project(feed_domain="feeds.example.com")

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

`start`, `end`, and other temporal fields accept ISO 8601 strings or
`datetime.date` / `datetime.datetime` objects; timezone-aware UTC datetimes
serialize with a `Z` suffix.

`list_groups()`, `list_feeds()`, `list_events()`, and `list_subscribers()`
return plain Python lists. When the server returns a paginated REST envelope,
the helpers follow `next` links and collect every page for you.

Detail helpers are available for mutable resources: `get_*`, `update_*`, and
`delete_*` for groups and feeds, plus `get_subscriber()` and
`update_subscriber()`. Feed and group slugs are immutable server-side; subscriber
tokens and active state are managed through explicit lifecycle helpers.

## Async

Every helper is also available on `AsyncCruxPass` with the same signatures:

```python
import asyncio

from cruxpass import AsyncCruxPass


async def main() -> None:
    async with AsyncCruxPass(api_key="pk_...") as client:
        feeds = await client.list_feeds()
        print(feeds)


asyncio.run(main())
```

## Feed reads

Public subscriber feeds are fetched without auth and support conditional
requests via `ETag` and `Last-Modified` validators:

```python
feed = client.get_subscriber_feed(subscriber["token"])

print(feed.status_code)
print(feed.etag)
print(feed.text)

not_modified = client.get_subscriber_feed(
    subscriber["token"],
    etag=feed.etag,
)

assert not_modified.status_code == 304
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

## Errors and retries

API failures raise typed exceptions carrying `status_code`, `message`, and the
underlying `httpx.Response`:

```python
from cruxpass import AuthenticationError, NotFoundError

try:
    client.get_project()
except AuthenticationError:
    ...  # bad or revoked API key
except NotFoundError:
    ...
```

Connect errors and 429/502/503/504 responses are retried with exponential
backoff (honoring `Retry-After`). Tune or disable with
`CruxPass(..., max_retries=0)`.

## Configuration

| Option | Constructor | Environment | Default |
|---|---|---|---|
| API key | `api_key` | `CRUXPASS_API_KEY` | required |
| Base URL | `base_url` | `CRUXPASS_BASE_URL` | `https://cruxpass.com` |
| Timeout | `timeout` | | `10.0` seconds |
| Retries | `max_retries` | | `2` |
| HTTP client | `http_client` | | owned `httpx.Client` |

## Helpers

The client exposes the documented REST surface:

- `get_project()` / `update_project(feed_domain=...)`
- `list_groups()` / `create_group(...)` / `get_group(...)` / `update_group(...)` / `delete_group(...)`
- `list_feeds()` / `create_feed(...)` / `get_feed(...)` / `update_feed(...)` / `delete_feed(...)`
- `list_subscribers()` / `create_subscriber(...)` / `get_subscriber(...)` / `update_subscriber(...)`
- `deactivate_subscriber(token)` / `rotate_subscriber_token(token)` / `refresh_subscriber_artifact(token)`
- `list_events(feed_slug=...)` / `upsert_event(...)` / `cancel_event(...)`
- `upsert_recurring_schedule(...)`
- `upsert_recurring_exception(...)`
- `move_recurring_occurrence(...)`
- `skip_recurring_occurrence(...)`
- `cancel_recurring_occurrence(...)`
- `get_subscriber_feed(token, etag=..., modified_since=...)`
- `get_subscriber_feed_ics(token)`

For API paths that do not have a named helper yet, use `client.request(method,
path, json=..., params=...)`.

## Development

The project is managed with [uv](https://docs.astral.sh/uv/) end to end:

```bash
uv sync --group dev
uv run python -m unittest discover -s tests
uv run --group dev ruff check .
uv run --group dev ruff format --check .
uv run --group dev ty check src tests
uv build
```

## Status

Pre-1.0 package. Releases are coordinated with the matching CruxPass server
contract; see `CHANGELOG.md` for endpoint, client method, and migration notes.
PyPI publishing is GitHub-only; see `RELEASE.md`.
