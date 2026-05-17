import pytest
import pytest_asyncio
import httpx
from unittest.mock import AsyncMock, patch

from app.services.fetcher import FetcherService
from app.core.exceptions import AppError

@pytest.fixture
def patch_retry():
    with patch("tenacity.nap.sleep", new_callable=AsyncMock) as mock_sleep:
        yield mock_sleep

@pytest_asyncio.fixture
async def fetcher():
    svc = FetcherService()
    # Intercept HTTP client with a stunt double
    svc.client.get = AsyncMock()
    yield svc
    await svc.close()

@pytest.mark.asyncio
async def test_fetcher_success(fetcher):
    # Setup healthy response
    response_mock = httpx.Response(
        status_code=200, 
        headers={"content-type": "text/html"},
        text='<html>Success</html>',
        request=httpx.Request("GET", "https://example.com")
    )
    fetcher.client.get.return_value = response_mock
    
    # Execute
    result = await fetcher.fetch("https://example.com")
    
    # Assert
    assert result.status_code == 200
    assert result.page_source == '<html>Success</html>'

@pytest.mark.asyncio
async def test_fetcher_timeout_retries_and_fails(fetcher, patch_retry):
    fetcher.client.get.side_effect = httpx.TimeoutException("Timeout")
    
    with pytest.raises(AppError) as exc_info:
        await fetcher.fetch("https://example.com")
        
    assert exc_info.value.status_code == 504
    assert exc_info.value.error_code == "REQUEST_TIMEOUT"
    # Tenacity retries 3 attempts
    assert fetcher.client.get.call_count == 3
    