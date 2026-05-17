import pytest
from unittest.mock import AsyncMock

from app.main import app
from app.dependencies import get_metadata_service
from app.core.exceptions import AppError


@pytest.fixture
def mock_service():
    mock = AsyncMock()
    app.dependency_overrides[get_metadata_service] = lambda: mock
    yield mock
    app.dependency_overrides.clear()


class TestAppErrorHandler:

    def test_custom_error_maps_to_status_code(self, test_client, mock_service):
        mock_service.create_metadata.side_effect = AppError(
            message="Custom error", error_code="CUSTOM_ERROR", status_code=418,
        )

        resp = test_client.post("/api/v1/metadata/", json={"url": "https://example.com"})
        assert resp.status_code == 418
        assert resp.json()["error"]["code"] == "CUSTOM_ERROR"

    def test_ssrf_blocked_returns_403(self, test_client, mock_service):
        from app.core.exceptions import SSRFBlockedError
        mock_service.create_metadata.side_effect = SSRFBlockedError()

        resp = test_client.post("/api/v1/metadata/", json={"url": "https://example.com"})
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "SSRF_BLOCKED"


class TestValidationErrorHandler:

    def test_missing_field_returns_422(self, test_client):
        resp = test_client.post("/api/v1/metadata/", json={})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


class TestGenericExceptionHandler:

    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_500(self):
        from app.core.exception_handlers import generic_exception_handler
        resp = await generic_exception_handler(None, RuntimeError("unexpected"))
        assert resp.status_code == 500
        import json
        assert json.loads(resp.body)["error"]["code"] == "INTERNAL_SERVER_ERROR"
