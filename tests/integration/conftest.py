import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

from testcontainers.mongodb import MongoDbContainer
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.models.metadata import MetadataRecord
from app.repositories.metadata import MetadataRepository
from app.services.metadata import MetadataService
from app.services.fetcher import FetcherService
from app.workers.background_worker import BackgroundWorker


# ── Override the root conftest's mock so integration tests
#    connect to a real MongoDB instead. ──────────────────────
@pytest.fixture(autouse=True)
def mock_db_lifespan():
    yield


# ── Docker MongoDB container (session-scoped) ───────────────
@pytest.fixture(scope="session")
def mongo_container():
    with MongoDbContainer("mongo:7.0") as mongo:
        yield mongo


@pytest.fixture(scope="session")
def mongo_url(mongo_container):
    return mongo_container.get_connection_url()


# ── Configure app settings once at session start ────────────
@pytest.fixture(scope="session", autouse=True)
def _patch_settings(mongo_url):
    from app.core.config import settings
    settings.mongodb_url = mongo_url
    settings.database_name = "test_integration"


# ── Per-test Beanie initialisation ──────────────────────────
@pytest_asyncio.fixture
async def beanie(mongo_url):
    """
    Initialises Beanie against the test database and cleans
    the collection after the test.
    """
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
    client.append_metadata = lambda _: None

    from app.core.config import settings
    await init_beanie(
        database=client[settings.database_name],
        document_models=[MetadataRecord],
    )

    yield

    await client.drop_database(settings.database_name)
    client.close()


# ── Domain-object fixtures ─────────────────────────────────
@pytest.fixture
def repository(beanie):
    return MetadataRepository()


@pytest.fixture
def background_worker():
    return BackgroundWorker(limit=10)


@pytest_asyncio.fixture
async def mocked_fetcher():
    svc = FetcherService()
    await svc.client.aclose()
    svc.client = AsyncMock()
    svc.client.get.return_value = AsyncMock(
        status_code=200,
        headers={"content-type": "text/html"},
        cookies={},
        text="<html>ok</html>",
    )
    return svc


@pytest_asyncio.fixture
async def metadata_service(repository, mocked_fetcher, background_worker):
    return MetadataService(
        repository=repository,
        fetch_service=mocked_fetcher,
        worker=background_worker,
    )


@pytest.fixture(scope="session")
def test_client(mongo_url):
    """
    FastAPI TestClient connected to the real MongoDB.
    Waits for MongoDB to accept connections before creating
    the client (so the lifespan's connect_db does not fail).
    """
    import time
    from pymongo import MongoClient

    time.sleep(3)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            c = MongoClient(mongo_url, serverSelectionTimeoutMS=2000)
            c.admin.command("ping")
            c.close()
            break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError("MongoDB not ready within timeout")

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        yield client
