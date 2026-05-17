# Design Decisions

A quick walkthrough of the decisions I made while building this service and why I made them.

---

## 1. Two endpoints instead of one

The assignment asks for a POST that fetches and stores, and a GET that either returns cached data or acknowledges the request and moves on. These two have fundamentally different behaviour — one blocks, one doesn't — so I kept them as separate endpoints rather than trying to cram both behaviours into one.

| Endpoint | What it does |
|---|---|
| `POST /metadata/` | Fetches the URL, stores everything, returns 201 with the full result |
| `GET /metadata?url=` | Returns 200 if already cached, or 202 and kicks off a background job |

---

## 2. Background worker — pure asyncio, no Celery

The assignment specifically says no external service-to-self HTTP calls and no polling loops. So I wrote a small `BackgroundWorker` class that runs tasks using plain `asyncio` — no Redis, no Celery 

The interesting part is `schedule_once`. If 10 people request the same uncached URL at the same time, I don't want 10 fetches happening in parallel. `schedule_once` checks if a task for that URL is already running and reuses it if so. Only one fetch goes out, everyone waits on the same result.

```python
async def schedule_once(self, key: str, coro_factory: Callable) -> asyncio.Task:
    async with self._lock:
        existing = self._tasks_by_key.get(key)
        if existing and not existing.done():
            return existing
        task = asyncio.create_task(self._run(coro_factory()))
        self._tasks_by_key[key] = task
```

I also put a semaphore on the worker (default 10) so a burst of requests doesn't open 100 connections at once and exhaust the pool.

> ⚠️ **Known trade-off:** This only works in a single process. If you scale horizontally behind a load balancer, each instance has its own task map and dedup breaks. At that point you'd need Redis or a proper queue. For this scope, it's fine.

---

## 3. How I structured the code

I tried to keep things in clear layers so each part only knows what it needs to:

- **Routes** (`app/api/`) — just HTTP. Parse the request, call the service, return the response.
- **Services** (`app/services/`) — the actual logic. Decide what to fetch, when, how.
- **Repository** (`app/repositories/`) — all database calls live here, nowhere else.
- **Workers** (`app/workers/`) — background task scheduling.
- **Core** (`app/core/`) — config, logging, security, exceptions.

The repository pattern in particular was useful. Services never call MongoDB directly, so I could unit test them by just swapping in a mock repository. No real database needed for most tests.

---

## 4. MongoDB schema and the state machine

For the document structure I went with:

```
url (unique, indexed)
status: PENDING | FETCHING | DONE | ERROR
headers: dict
cookies: dict
page_source: str
status_code: int
error_message: str
fetched_at, created_at, updated_at
```

The `url` field has a unique index so lookups stay fast as the collection grows.

I used a four-state machine instead of a boolean `fetched` flag. A boolean can't tell you "currently being fetched" or "it failed" — both of which a polling client needs to know. The states are:

```
PENDING → FETCHING → DONE
                   → ERROR → PENDING  (can retry without deleting the record)
```

---

## 5. Handling things that go wrong

A few things I added to keep the service stable:

**Retries** — external URLs are unreliable. I wrapped the fetch in tenacity with 3 attempts and exponential backoff (1s, 2s, 4s). Only retries on network errors like timeouts and connection failures — not on 4xx responses, because those are real errors that shouldn't be silently retried.

**Response guards** — reject anything over 2 MB and anything that isn't `text/html`. Prevents someone pointing the service at a large binary file and exhausting memory.

**Docker health checks** — `depends_on: condition: service_healthy` so the API waits for MongoDB to actually be ready before starting, not just "the container started".

---

## 6. URL normalisation

`https://amazon.com` and `https://www.amazon.com` are the same page but without normalisation they'd be two separate DB records. I normalise every URL at the service layer before touching the database — strip `www.`, lowercase the hostname, remove default ports, strip fragments.

| What came in | What gets stored |
|---|---|
| `https://www.amazon.com` | `https://amazon.com/` |
| `https://Amazon.COM/` | `https://amazon.com/` |
| `https://amazon.com:443/` | `https://amazon.com/` |
| `https://amazon.com#reviews` | `https://amazon.com/` |

I put this in the service layer rather than the API layer so it applies regardless of how the service is called in the future.

---

## 7. Centralised response shape

I wanted every response — success or failure — to come back in the same shape so clients always know what to expect. Everything goes through `success_response()` and `error_response()` helpers, never constructed manually in routes.

Success:
```json
{
  "success": true,
  "message": "Metadata fetched successfully",
  "data": { "url": "https://example.com", "status": "DONE", "..." }
}
```

Failure:
```json
{
  "success": false,
  "message": "Blocked internal/private IP",
  "error": { "code": "SSRF_BLOCKED", "details": null }
}
```

Three global exception handlers make sure every error ends up in this shape — business errors, Pydantic validation errors, and anything unexpected. No try/except scattered across routes, and the 500 handler never leaks the actual exception or stack trace to the client.

---

## 8. SSRF protection

Since users supply the URLs, the server could be tricked into fetching internal addresses — things like `169.254.169.254` (cloud metadata endpoint) or `localhost:27017` (the database itself).

To prevent that, I resolve the hostname to an IP before making any request and reject it if it falls in a private, loopback, or link-local range.

```python
ip = socket.gethostbyname(hostname)
ip_obj = ipaddress.ip_address(ip)
if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast:
    raise SSRFBlockedError()
```

String matching the hostname isn't enough — an attacker can use things like `127.0.0.1.nip.io` which looks fine as a string but resolves to loopback. Checking the actual resolved IP is the only reliable way. I also re-run this check on every redirect hop, not just the original URL, so a redirect chain can't be used to sneak past the guard.

---

## 9. Logging

I used `structlog` instead of plain `logging` so every log line is a proper key-value dict rather than a formatted string. The big win is `contextvars` — I bind `request_id` and `url` once at the start of a request and they automatically appear on every log line within that request. No passing context through function arguments.

In dev it prints colourised human-readable output. In production it switches to JSON for log aggregators. Just an environment variable flip, no code changes.

---

## 10. Tests

I wrote tests at three levels:

| Level | Count | What it covers |
|---|---|---|
| Unit | 17 | Each service and the worker tested in isolation with mocks |
| API | 5 | Full request/response cycle via FastAPI's test client |
| Integration | 16+ | Real MongoDB via testcontainers, actual concurrent requests |

The integration tests are the most interesting part. I specifically wrote tests that fire 10 concurrent requests at the same uncached URL and assert that only one fetch happened and only one document was created. Race conditions don't show up in normal tests — you have to deliberately create the concurrency to catch them.

---

## Other smaller decisions

- **Atomic upsert via `$setOnInsert`** — concurrent requests for the same new URL won't race into a `DuplicateKeyError`. `$setOnInsert` only writes the initial fields when the document is being created for the first time; if it already exists it just returns it. Makes `get_or_create` safe under concurrency in a single DB operation.

- **MongoDB + Beanie over PostgreSQL** — website metadata is semi-structured by nature. Some pages have OpenGraph tags, some have Twitter cards, some have neither. Fitting that into a rigid relational schema would mean constant migrations. Beanie on top of Motor adds Pydantic validation at the DB boundary so malformed data never gets written.


- **Layered connection pools** — three independent limits each protecting a different resource: `httpx.AsyncClient(max_connections=100)` for outbound HTTP, `AsyncIOMotorClient(maxPoolSize=20)` for MongoDB, and `asyncio.Semaphore(10)` on the background worker. A burst of requests hits the semaphore first; if it gets through, the HTTP and DB pools stop it going further.

- **Dependency injection via FastAPI `Depends`** — all collaborators (repository, fetcher, worker) are wired once in `dependencies.py` and injected into services. Routes stay thin, services stay testable, and swapping a dependency means changing one place.

- **12-factor config** (`app/core/config.py`) — all settings from environment variables via `pydantic-settings`. Automatic type coercion (string `"10"` → int `10`), validation at startup, identical behaviour across dev, staging, and production.
