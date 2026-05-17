# Architecture

This document describes the system's structure, component relationships, and runtime data flow. For the rationale behind each design decision, see [DESIGN_CHOICES.md](DESIGN_CHOICES.md).

---

## High-Level Diagram

```
[Client] <── HTTP/JSON ──> [FastAPI Server] <── Motor/Beanie ──> [MongoDB]
                                │
                        [BackgroundWorker]
                        (asyncio tasks)
                                │
                         [Target URLs]
```

---

## Directory Structure

```
app/
├── main.py                      # FastAPI entry point, lifespan, exception handlers
├── dependencies.py              # Singleton wiring (DI)
├── api/routes/
│   ├── metadata.py              # POST /metadata/, GET /metadata/
│   └── health.py                # GET /health
├── core/
│   ├── config.py                # Pydantic settings (env-based)
│   ├── constants.py             # MAX_RESPONSE_SIZE (2 MB)
│   ├── exceptions.py            # AppError, SSRFBlockedError
│   ├── exception_handlers.py    # Global error responses
│   ├── responses.py             # Unified ApiResponse schema
│   ├── security.py              # SSRF validation
│   └── logger.py                # structlog configuration
├── database/
│   ├── db.py                    # Motor client lifecycle
│   └── __init__.py              # Beanie initialization
├── models/
│   └── metadata.py              # MetadataRecord (Beanie Document)
├── schemas/
│   └── metadata.py              # Request/response Pydantic models
├── repositories/
│   └── metadata.py              # Data access layer (5 atomic operations)
├── services/
│   ├── metadata.py              # Orchestration (create/get metadata)
│   └── fetcher.py               # External HTTP fetcher with retry
└── workers/
    └── background_worker.py     # asyncio task scheduler with dedup
```

---

## Component Layers

### 1. API Layer (`api/routes/`)
- Two endpoints: `POST /metadata/` (synchronous) and `GET /metadata/` (async polling)
- Routes delegate to `MetadataService` via FastAPI's `Depends`
- Three global exception handlers catch every error type and return a consistent JSON schema

### 2. Service Layer (`services/`)
- **`MetadataService`** — orchestrates the fetch lifecycle: atomic DB lookup, worker scheduling, result propagation
- **`FetcherService`** — makes external HTTP requests using `httpx`, validates SSRF, enforces response size and content-type limits

### 3. Background Worker (`workers/background_worker.py`)
- Pure `asyncio`-based task scheduler — no Celery, no Redis
- `asyncio.Semaphore` limits concurrent executions (default 10)
- `schedule_once(key, coro_factory)` ensures only one task runs per URL at any time; concurrent callers reuse the same task

### 4. Data Layer (`repositories/` + MongoDB)
- **`MetadataRepository`** encapsulates all database access: `get_or_create`, `reset_to_pending`, `update_status`, `update_metadata`, `update_error`
- All operations use atomic MongoDB primitives (`upsert`, `$setOnInsert`)
- **MongoDB** stores semi-structured metadata naturally (variable schemas per website)
- **Beanie** provides Pydantic validation at the database boundary

### 5. Core Utilities (`core/`)
- **Security**: DNS-resolution-based SSRF validation blocks private/loopback/link-local/multicast IPs
- **Logging**: `structlog` with request-scoped context — colorized console in dev, JSON in production
- **Error handling**: Unified `ApiResponse` schema, three global handlers (AppError, ValidationError, unhandled Exception)

---

## Data Flow

### POST `/metadata/` (Synchronous)

```
Client → POST /metadata/
  → MetadataService.create_metadata(url)
    → Repository.get_or_create(url)        # atomic upsert
    → Repository.reset_to_pending(url)     # if previously DONE
    → Worker.schedule_once(url, factory)   # deduplicate concurrent requests
    → FetcherService.fetch(url)            # SSRF check → HTTP GET → retry
    → Repository.update_metadata(...)      # store result, status → DONE
  ← 201 + MetadataResponse
```

### GET `/metadata/` (Async Polling)

```
Client → GET /metadata/?url=
  → MetadataService.get_metadata(url)
    → Repository.get_by_url(url)
    ├── If DONE → 200 + MetadataResponse
    └── If not DONE:
      → Repository.get_or_create(url)       # ensure PENDING record exists
      → Worker.schedule_once(url, factory)  # fire-and-forget background fetch
      ← 202 + AcceptedResponse
```

---

## Testing Layers

| Layer | Scope |
|---|---|
| **Unit** (17 tests) | Services, worker, fetcher, response models in isolation |
| **API** (5 tests) | Route integration, status codes, serialization via TestClient |
| **Integration** (16+ tests) | Real MongoDB (testcontainers), concurrency, race conditions |

For the rationale behind test structuring and concurrency coverage, see [DESIGN_CHOICES.md](DESIGN_CHOICES.md#11-testing-strategy-three-layers).
