import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.schemas.metadata import FetchedMetadata
from app.core.exceptions import AppError
from app.core.config import settings
from app.core.security import validate_ssrf
from app.core.constants import MAX_RESPONSE_SIZE,MAX_REDIRECT
from app.core.logger import get_logger
logger = get_logger(__name__)


class FetcherService:

    def __init__(self):

        timeout = httpx.Timeout(
            connect=5.0,
            read=float(settings.request_timeout),
            write=5.0,
            pool=5.0,
        )

        limits = httpx.Limits(
            max_connections=100,
            max_keepalive_connections=20,
        )

        self.client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            follow_redirects=False,
        )


    async def fetch(
        self,
        url: str,
    ) -> FetchedMetadata:

        try:
            return await self._execute_fetch(url)

        except httpx.TimeoutException:

            logger.exception("Request timeout", url=url)

            raise AppError(
                message="Request timed out",
                error_code="REQUEST_TIMEOUT",
                status_code=504,
            )

        except httpx.HTTPStatusError as e:

            logger.exception(
                "HTTP error response",
                url=url,
                status_code=e.response.status_code,
            )

            raise AppError(
                message="Upstream service error",
                error_code="UPSTREAM_HTTP_ERROR",
                status_code=502,
            )

        except httpx.ConnectError:

            logger.exception("Connection failed", url=url)

            raise AppError(
                message="Failed to connect",
                error_code="CONNECTION_ERROR",
                status_code=502,
            )

        except httpx.RequestError:

            logger.exception("Request failed", url=url)

            raise AppError(
                message="External request failed",
                error_code="REQUEST_FAILED",
                status_code=500,
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=10,
        ),
        retry=retry_if_exception_type(
            (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.ReadError,
            )
        ),
        reraise=True,
    )
    async def _execute_fetch(self, url: str) -> FetchedMetadata:
        current_url = url
        for _ in range(MAX_REDIRECT):
            validate_ssrf(current_url)
            response = await self.client.get(current_url)

            if response.is_redirect:
                redirect_url = response.headers.get("location")
                if not redirect_url:
                    raise AppError(
                        message="Invalid redirect response",
                        error_code="INVALSID_REDIRECT",
                        status_code=502,
                    )
                redirect_url = str(httpx.URL(current_url).join(redirect_url))
                current_url = redirect_url
                continue

            # Check status first — no point reading body of a 4xx/5xx
            response.raise_for_status()

            content = await response.aread()
            if len(content) > MAX_RESPONSE_SIZE:
                raise AppError(
                    message="Response too large",
                    error_code="RESPONSE_TOO_LARGE",
                    status_code=413,
                )

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                raise AppError(
                    message="Unsupported content type",
                    error_code="INVALID_CONTENT_TYPE",
                    status_code=400,
                )

            return FetchedMetadata(
                url=str(response.url),
                status_code=response.status_code,
                headers=dict(response.headers),
                cookies=dict(response.cookies),
                page_source=response.text,
            )

        raise AppError(
            message="Too many redirects",
            error_code="TOO_MANY_REDIRECTS",
            status_code=508,
        )
        


    async def close(self):

        await self.client.aclose()