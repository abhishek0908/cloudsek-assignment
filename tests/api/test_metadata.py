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


def test_create_metadata(test_client, mock_service):
    mock_response_data = {
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
    mock_service.create_metadata.return_value = mock_response_data

    payload = {"url": "https://example.com"}
    response = test_client.post("/metadata/", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["url"] == "https://example.com"
    mock_service.create_metadata.assert_called_once_with(
        "https://example.com/",
    )


def test_get_metadata_done(test_client, mock_service):
    """GET returns 200 when metadata is already available (DONE)."""
    mock_response_data = {
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
    mock_service.get_metadata.return_value = mock_response_data

    response = test_client.get(
        "/metadata/",
        params={"url": "https://example.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["url"] == "https://example.com"
    mock_service.get_metadata.assert_called_once_with(
        "https://example.com/",
    )


def test_get_metadata_pending(test_client, mock_service):
    """GET returns 202 when metadata is pending / being fetched."""
    from app.schemas.metadata import AcceptedResponse

    mock_service.get_metadata.return_value = AcceptedResponse(
        message="Metadata not found, fetch has been scheduled",
        url="https://example.com/",
        status=FetchStatus.PENDING,
    )

    response = test_client.get(
        "/metadata/",
        params={"url": "https://example.com"},
    )

    assert response.status_code == 202
    data = response.json()
    assert data["success"] is True
    assert data["data"]["url"] == "https://example.com/"
    mock_service.get_metadata.assert_called_once_with(
        "https://example.com/",
    )


def test_create_metadata_malformed(test_client):
    payload = {"url": "not-a-valid-url"}
    response = test_client.post("/metadata/", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
