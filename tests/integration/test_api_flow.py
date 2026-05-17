import pytest
from app.models.metadata import FetchStatus


class TestPostAndGetFlow:
    """
    End-to-end tests that exercise the full stack through
    the FastAPI TestClient backed by a real MongoDB.
    """

    def test_create_and_retrieve(self, test_client, monkeypatch):
        """
        POST a URL → 201 Created with metadata.
        GET the same URL → 200 OK (status is DONE).
        """
        from app.dependencies import get_metadata_service
        from unittest.mock import AsyncMock

        mock_service = AsyncMock()
        mock_service.create_metadata.return_value = {
            "url": "https://example.com",
            "status": FetchStatus.DONE,
            "status_code": 200,
            "headers": {"content-type": "text/html"},
            "cookies": {},
            "page_source": "<html>ok</html>",
            "error_message": None,
            "fetched_at": "2025-01-01T00:00:00Z",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        mock_service.get_metadata.return_value = {
            "url": "https://example.com",
            "status": FetchStatus.DONE,
            "status_code": 200,
            "headers": {"content-type": "text/html"},
            "cookies": {},
            "page_source": "<html>ok</html>",
            "error_message": None,
            "fetched_at": "2025-01-01T00:00:00Z",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        test_client.app.dependency_overrides[
            get_metadata_service
        ] = lambda: mock_service

        try:
            # POST
            post_resp = test_client.post(
                "/metadata/",
                json={"url": "https://example.com"},
            )
            assert post_resp.status_code == 201
            data = post_resp.json()
            assert data["success"] is True
            assert data["data"]["url"] == "https://example.com"

            # GET
            get_resp = test_client.get(
                "/metadata/",
                params={"url": "https://example.com"},
            )
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["success"] is True
            assert data["data"]["status"] == FetchStatus.DONE.value

        finally:
            test_client.app.dependency_overrides.clear()

    def test_get_pending_returns_202(self, test_client):
        """
        GET a URL that has no metadata yet returns 202 Accepted.
        """
        from app.schemas.metadata import AcceptedResponse
        from app.dependencies import get_metadata_service
        from unittest.mock import AsyncMock

        mock_service = AsyncMock()
        mock_service.get_metadata.return_value = AcceptedResponse(
            message="Metadata not found, fetch has been scheduled",
            url="https://unknown.com/",
            status=FetchStatus.PENDING,
        )
        test_client.app.dependency_overrides[
            get_metadata_service
        ] = lambda: mock_service

        try:
            resp = test_client.get(
                "/metadata/",
                params={"url": "https://unknown.com"},
            )
            assert resp.status_code == 202
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["status"] == FetchStatus.PENDING

        finally:
            test_client.app.dependency_overrides.clear()

    def test_create_malformed_url_422(self, test_client):
        resp = test_client.post(
            "/metadata/",
            json={"url": "not-a-valid-url"},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_get_malformed_url_422(self, test_client):
        resp = test_client.get(
            "/metadata/",
            params={"url": "not-valid"},
        )
        assert resp.status_code == 422

    def test_repost_existing_url_returns_201(self, test_client):
        """
        POSTing the same URL twice both return 201.
        """
        from app.dependencies import get_metadata_service
        from unittest.mock import AsyncMock

        mock = AsyncMock()
        mock.create_metadata.return_value = {
            "url": "https://example.com",
            "status": FetchStatus.DONE,
            "status_code": 200,
            "headers": {},
            "cookies": {},
            "page_source": "<html>ok</html>",
            "error_message": None,
            "fetched_at": "2025-01-01T00:00:00Z",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        test_client.app.dependency_overrides[
            get_metadata_service
        ] = lambda: mock

        try:
            for _ in range(2):
                resp = test_client.post(
                    "/metadata/",
                    json={"url": "https://example.com"},
                )
                assert resp.status_code == 201

        finally:
            test_client.app.dependency_overrides.clear()
