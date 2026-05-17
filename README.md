# CloudSEK Assignment — HTTP Metadata Inventory Service

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)]()
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-brightgreen)]()
[![docker](https://img.shields.io/badge/docker-compose-blue)]()

An asynchronous REST API that extracts, caches, and serves website metadata (headers, cookies, page source) from user-supplied URLs. Built with **FastAPI**, **MongoDB**, and pure **asyncio** — no external message brokers.

---

## Quick Start

```bash
docker compose up -d --build
curl -X POST http://localhost:8000/api/v1/metadata/ \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com"}'
```

Interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Setup

### Docker (Recommended)

Spins up both the API and MongoDB in containers.

```bash
cp .env.example .env
docker compose up -d --build
```

The API is at `http://localhost:8000`, docs at `http://localhost:8000/docs`.  
To stop: `docker compose down`

### Local Python Environment

**Prerequisites**: Python 3.10+, a running MongoDB instance.

```bash
cp .env.example .env
# Update MONGODB_URL in .env, e.g. mongodb://localhost:27017/metadata_db

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Running Tests

```bash
pytest                  # all tests
make test               # all tests
make test-unit          # unit tests only
make test-integration   # integration tests (requires Docker for MongoDB)
```

---

## API Endpoints

| Method | Path | Behavior |
|---|---|---|
| `POST` | `/api/v1/metadata/` | Blocks until metadata is fetched — returns 201 |
| `GET` | `/api/v1/metadata/?url=` | Returns 200 (cached) or 202 (background fetch scheduled) |
| `GET` | `/api/v1/health` | Liveness probe |

### `POST /api/v1/metadata/` — Synchronous Fetch

```bash
curl -s -X POST http://localhost:8000/api/v1/metadata/ \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com"}' | jq
```

**Response** (201):

```json
{
  "success": true,
  "message": "Metadata processing completed",
  "data": {
    "url": "https://example.com",
    "status": "done",
    "status_code": 200,
    "headers": {
      "content-type": "text/html; charset=utf-8",
      "server": "ECS (dcb/7F14)",
      ...
    },
    "cookies": {},
    "page_source": "<!DOCTYPE html>...",
    "error_message": null,
    "fetched_at": "2026-05-17T10:00:00Z",
    "created_at": "2026-05-17T10:00:00Z",
    "updated_at": "2026-05-17T10:00:00Z"
  }
}
```

**Error** (422 — validation):

```json
{
  "success": false,
  "message": "Invalid request payload",
  "error": {
    "code": "VALIDATION_ERROR",
    "details": [
      {
        "type": "url_parsing",
        "loc": ["body", "url"],
        "msg": "Input should be a valid URL"
      }
    ]
  }
}
```

**Error** (403 — SSRF blocked):

```json
{
  "success": false,
  "message": "Blocked internal/private IP",
  "error": { "code": "SSRF_BLOCKED" }
}
```

### `GET /api/v1/metadata/?url=` — Async Polling

```bash
# First call — metadata not cached, returns 202
curl -s "http://localhost:8000/api/v1/metadata/?url=https://example.com" | jq
```

**Response** (202 — fetch scheduled):

```json
{
  "success": true,
  "message": "Metadata not found, fetch has been scheduled",
  "data": {
    "url": "https://example.com",
    "status": "pending"
  }
}
```

```bash
# Second call — metadata is now cached, returns 200
curl -s "http://localhost:8000/api/v1/metadata/?url=https://example.com" | jq
```

**Response** (200 — cached):

```json
{
  "success": true,
  "message": "Metadata fetched successfully",
  "data": {
    "url": "https://example.com",
    "status": "done",
    "status_code": 200,
    "headers": { ... },
    "cookies": {},
    "page_source": "<!DOCTYPE html>...",
    "error_message": null,
    "fetched_at": "2026-05-17T10:00:00Z",
    "created_at": "2026-05-17T10:00:00Z",
    "updated_at": "2026-05-17T10:00:00Z"
  }
}
```

### `GET /api/v1/health` — Liveness Probe

```bash
curl -s http://localhost:8000/api/v1/health | jq
```

**Response** (200):

```json
{
  "status": "healthy"
}
```

---

## Documentation

| Document | What it covers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System structure, component layers, data flow |
| [DESIGN_CHOICES.md](DESIGN_CHOICES.md) | Every engineering trade-off and why it was made |

---

## Tech Stack

**Runtime:** Python 3.11 · FastAPI · Uvicorn · Pydantic  
**Database:** MongoDB 7.0 · Motor · Beanie (ODM)  
**HTTP:** httpx · Tenacity (retry)  
**Infra:** Docker · Docker Compose  
**Testing:** pytest · pytest-asyncio · TestClient · testcontainers
