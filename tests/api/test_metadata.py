import pytest
from app.models.metadata import FetchStatus
from unittest.mock import AsyncMock
from app.main import app
from app.dependencies import get_metadata_service


@pytest.fixture
def mock_service():
    mock = AsyncMock()
    app.dependency_overrides[get_metadata_service] = lambda: mock
    yield mock
    app.dependency_overrides.clear()


def _done_response():
    return {
        "url": "https://example.com",
        "status": FetchStatus.DONE,
        "status_code": 200,
        "headers": {},
        "cookies": {},
        "page_source": "<html></html>",
        "error_message": None,
        "fetched_at": "2023-01-01T00:00:00Z",
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
    }


class TestCreateMetadata:

    def test_valid_url_returns_201(self, test_client, mock_service):
        mock_service.create_metadata.return_value = _done_response()

        resp = test_client.post("/api/v1/metadata/", json={"url": "https://example.com"})

        assert resp.status_code == 201
        assert resp.json()["success"] is True
        mock_service.create_metadata.assert_called_once_with("https://example.com/")

    def test_malformed_url_returns_422(self, test_client):
        resp = test_client.post("/api/v1/metadata/", json={"url": "not-a-valid-url"})

        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_missing_field_returns_422(self, test_client):
        resp = test_client.post("/api/v1/metadata/", json={})

        assert resp.status_code == 422


class TestGetMetadata:

    def test_done_returns_200(self, test_client, mock_service):
        mock_service.get_metadata.return_value = _done_response()

        resp = test_client.get("/api/v1/metadata/", params={"url": "https://example.com"})

        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == FetchStatus.DONE.value

    def test_pending_returns_202(self, test_client, mock_service):
        from app.schemas.metadata import AcceptedResponse

        mock_service.get_metadata.return_value = AcceptedResponse(
            url="https://example.com/", status=FetchStatus.PENDING,
        )

        resp = test_client.get("/api/v1/metadata/", params={"url": "https://example.com"})

        assert resp.status_code == 202
        assert resp.json()["data"]["status"] == FetchStatus.PENDING.value

    def test_missing_param_returns_422(self, test_client):
        resp = test_client.get("/api/v1/metadata/")

        assert resp.status_code == 422
