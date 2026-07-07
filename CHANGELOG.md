# Changelog

All notable CruxPass Python client contract changes are documented here.

## 0.0.4 - Pending coordinated server release

Modernization release coordinated with the CruxPass server production-readiness
contract updates.

Breaking changes:

- Requires Python 3.13 or newer (previously 3.9+).
- The HTTP layer moved from `requests` to `httpx`. `APIError.response` is now
  an `httpx.Response`, and the `session` constructor argument was replaced by
  `http_client` (an `httpx.Client`). `FeedResponse.headers` is now
  `httpx.Headers`.

Added:

- `AsyncCruxPass`, an async client mirroring every sync helper.
- Automatic retries with exponential backoff and `Retry-After` support for
  connect errors and 429/502/503/504 responses; tune with `max_retries`
  (default 2, set 0 to disable). Safe because CruxPass writes are idempotent
  upserts keyed by `external_id`.
- Typed error subclasses: `AuthenticationError` (401/403), `NotFoundError`
  (404), `RateLimitError` (429), and `ServerError` (5xx), all subclasses of
  `APIError`.
- `CRUXPASS_API_KEY` and `CRUXPASS_BASE_URL` environment variable fallbacks.
- Context manager support on both clients and an explicit `close()`.
- A `User-Agent` header of `cruxpass-python/<version>` on API requests.
- `request()` now accepts relative paths and returns `None` for empty bodies.
- `list_events(feed_slug=...)` for `GET /api/feeds/{feed_slug}/events/`.
- `list_groups()`, `list_feeds()`, `list_events()`, and `list_subscribers()`
  consume paginated REST envelopes and still accept the legacy raw list shape.
- Detail lifecycle helpers: `get_group()`, `update_group()`, `delete_group()`,
  `get_feed()`, `update_feed()`, `delete_feed()`, `get_subscriber()`, and
  `update_subscriber()`.
- `upsert_recurring_schedule(..., timezone=...)` for IANA timezone-aware
  recurrence expansion.

Server contract:

- REST list endpoints may return paginated envelopes with `count`, `next`,
  `previous`, and `results`.
- `GET /api/feeds/{feed_slug}/events/` lists one-off events for a feed.
- Groups and feeds have `GET`, `PATCH`, and `DELETE` detail endpoints.
- Subscribers have `GET` and `PATCH` detail endpoints; token and active state
  remain read-only.
- Recurring schedule payloads accept optional IANA `timezone`; all-day writes
  must use UTC-midnight datetimes.
- `/api/v1/` is an alias for the additive CruxPass v1 REST contract.

Tooling:

- Package builds use the `uv_build` backend; version metadata is single-sourced
  from `pyproject.toml`.
- CI lints with `ruff`, type checks with `ty`, tests on 3.13 and 3.14, and
  publishes with `pypa/gh-action-pypi-publish` trusted publishing.

Migration notes:

- Replace `session=...` with `http_client=httpx.Client(...)` if you injected a
  custom session.
- Code that touched `APIError.response` as a `requests.Response` should treat
  it as an `httpx.Response` (`.json()`, `.text`, `.headers` behave the same
  for common uses).

## 0.0.3 - Pending coordinated server release

Server contract:

- `GET /api/project/`
- `PATCH /api/project/`
- `GET /api/groups/`
- `POST /api/groups/`
- `GET /api/feeds/`
- `POST /api/feeds/`
- `POST /api/feeds/{feed_slug}/events/`
- `POST /api/feeds/{feed_slug}/recurring-schedules/`
- `POST /api/feeds/{feed_slug}/recurring-schedules/{schedule_external_id}/exceptions/`
- `GET /api/subscribers/`
- `POST /api/subscribers/`
- `POST /api/subscribers/{subscriber_token}/deactivate/`
- `POST /api/subscribers/{subscriber_token}/rotate-token/`
- `POST /api/subscribers/{subscriber_token}/refresh-artifact/`
- `GET /f/{subscriber_token}.ics`

Client methods:

- Added project settings helpers: `get_project()` and `update_project()`.
- Added subscriber lifecycle helpers: `deactivate_subscriber()`,
  `rotate_subscriber_token()`, and `refresh_subscriber_artifact()`.
- Added recurring schedule helpers: `upsert_recurring_schedule()`,
  `upsert_recurring_exception()`, `move_recurring_occurrence()`,
  `skip_recurring_occurrence()`, and `cancel_recurring_occurrence()`.
- Added public feed helper `get_subscriber_feed()` for ICS reads with `ETag`,
  `Last-Modified`, and conditional request support.
- Kept `get_subscriber_feed_ics()` as a convenience string-returning helper.

Migration notes:

- Requires the server contract that includes project-scoped API keys, project
  feed domains, subscriber artifact refresh, recurring schedules, and cache
  validators on public ICS feed responses.
- Existing one-off event, group, feed, subscriber, and `get_subscriber_feed_ics`
  integrations remain source compatible.

## 0.0.1 - Initial release

- Added a small requests-based client for groups, feeds, subscribers, one-off
  event upserts, event cancellation, and public ICS feed reads.
