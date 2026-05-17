# CloudSEK Assignment — HTTP Metadata Inventory Service

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)]()
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-brightgreen)]()
[![docker](https://img.shields.io/badge/docker-compose-blue)]()

An asynchronous REST API that extracts, caches, and serves website metadata (headers, cookies, page source) from user-supplied URLs. Built with **FastAPI**, **MongoDB**, and pure **asyncio**.

---

## Quick Start

```bash
git clone https://github.com/abhishek0908/cloudsek-assignment.git
cd cloudsek-assignment
cp .env.example .env
docker compose up -d --build
```

The API is at `http://localhost:8000`, docs at `http://localhost:8000/docs`.  
To stop: `docker compose down`

### Local Python Environment

**Prerequisites**: Python 3.11+, a running MongoDB instance.

```bash
cp .env.example .env
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
| `POST` | `/api/v1/metadata/` | `curl -X POST http://localhost:8000/api/v1/metadata/ -H 'Content-Type: application/json' -d '{"url": "https://example.com"}'` |
| `GET` | `/api/v1/metadata/?url=` | `curl "http://localhost:8000/api/v1/metadata/?url=https://example.com"` |
| `GET` | `/api/v1/health` | `curl http://localhost:8000/api/v1/health` |

---

## Documentation

| Document | What it covers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System structure, component layers, data flow |
| [DESIGN_CHOICES.md](DESIGN_CHOICES.md) | Engineering trade-offs and why they were made |

---

## Tech Stack

**Runtime:** Python 3.11 · FastAPI · Uvicorn · Pydantic  
**Database:** MongoDB 7.0 · Motor · Beanie (ODM)  
**HTTP:** httpx · Tenacity (retry)  
**Infra:** Docker · Docker Compose  
**Testing:** pytest · pytest-asyncio · TestClient · testcontainers
