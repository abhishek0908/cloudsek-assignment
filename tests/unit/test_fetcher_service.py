import pytest
import pytest_asyncio
import httpx
from unittest.mock import AsyncMock, patch

from app.services.fetcher import FetcherService
from app.core.exceptions import AppError


@pytest.fixture
def patch_retry():
    with patch("tenacity.nap.sleep", new_callable=AsyncMock):
        yield


@pytest_asyncio.fixture
async def fetcher():
    svc = FetcherService()
    svc.client.get = AsyncMock()
    yield svc
    await svc.close()


def _ok_response(url="https://example.com"):
    req = httpx.Request("GET", url)
    return httpx.Response(
        status_code=200,
        headers={"content-type": "text/html"},
        text="<html>OK</html>",
        request=req,
    )


class TestFetcher:

    @pytest.mark.asyncio
    async def test_successful_fetch(self, fetcher):
        fetcher.client.get.return_value = _ok_response()
        result = await fetcher.fetch("https://example.com")
        assert result.status_code == 200
        assert result.page_source == "<html>OK</html>"

    @pytest.mark.asyncio
    async def test_timeout_retries_and_fails(self, fetcher, patch_retry):
        fetcher.client.get.side_effect = httpx.TimeoutException("Timeout")

        with pytest.raises(AppError) as exc:
            await fetcher.fetch("https://example.com")
        assert exc.value.status_code == 504
        assert exc.value.error_code == "REQUEST_TIMEOUT"
        assert fetcher.client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_connect_error_retries_and_fails(self, fetcher, patch_retry):
        fetcher.client.get.side_effect = httpx.ConnectError("refused")

        with pytest.raises(AppError) as exc:
            await fetcher.fetch("https://example.com")
        assert exc.value.status_code == 502
        assert exc.value.error_code == "CONNECTION_ERROR"

    @pytest.mark.asyncio
    async def test_http_500_returns_502(self, fetcher):
        req = httpx.Request("GET", "https://example.com")
        fetcher.client.get.return_value = httpx.Response(
            status_code=500, request=req, headers={"content-type": "text/html"},
        )
        with pytest.raises(AppError) as exc:
            await fetcher.fetch("https://example.com")
        assert exc.value.error_code == "UPSTREAM_HTTP_ERROR"

    @pytest.mark.asyncio
    async def test_rejects_non_html(self, fetcher):
        req = httpx.Request("GET", "https://example.com")
        fetcher.client.get.return_value = httpx.Response(
            status_code=200, request=req,
            headers={"content-type": "application/json"},
            text='{"key": "val"}',
        )
        with pytest.raises(AppError) as exc:
            await fetcher.fetch("https://example.com")
        assert exc.value.error_code == "INVALID_CONTENT_TYPE"

    @pytest.mark.asyncio
    async def test_follows_single_redirect(self, fetcher):
        req = httpx.Request("GET", "https://example.com")
        redir = httpx.Response(
            status_code=302, request=req,
            headers={"location": "https://example.com/target", "content-type": "text/html"},
        )
        target_req = httpx.Request("GET", "https://example.com/target")
        target = httpx.Response(
            status_code=200, request=target_req,
            headers={"content-type": "text/html"}, text="<html>target</html>",
        )
        fetcher.client.get.side_effect = [redir, target]

        result = await fetcher.fetch("https://example.com")
        assert result.page_source == "<html>target</html>"

    @pytest.mark.asyncio
    async def test_too_many_redirects_raises(self, fetcher):
        req = httpx.Request("GET", "https://example.com")
        redir = httpx.Response(
            status_code=302, request=req,
            headers={"location": "https://example.com/loop", "content-type": "text/html"},
        )
        fetcher.client.get.return_value = redir

        with pytest.raises(AppError) as exc:
            await fetcher.fetch("https://example.com")
        assert exc.value.error_code == "TOO_MANY_REDIRECTS"

    @pytest.mark.asyncio
    async def test_ssrf_blocked(self, fetcher):
        from app.core.exceptions import SSRFBlockedError
        with patch("app.services.fetcher.validate_ssrf",
                   side_effect=SSRFBlockedError()):
            with pytest.raises(SSRFBlockedError):
                await fetcher.fetch("https://169.254.169.254/")
