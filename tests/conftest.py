import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

# Provide a mock lifespan automatically to block real Mongo connections
@pytest.fixture(autouse=True)
def mock_db_lifespan():
    with patch("app.main.connect_db", new_callable=AsyncMock), \
         patch("app.main.init_database", new_callable=AsyncMock), \
         patch("app.main.close_db", new_callable=AsyncMock):
        yield

@pytest.fixture
def test_client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        yield client
