import asyncio

from app.models.metadata import FetchStatus
from app.repositories.metadata import MetadataRepository
from app.services.fetcher import FetcherService
from app.workers.background_worker import BackgroundWorker
from app.schemas.metadata import AcceptedResponse
from app.core.logger import get_logger
from app.core.normalizer import normalize_url

logger = get_logger(__name__)


class MetadataService:

    def __init__(
        self,
        repository: MetadataRepository,
        fetch_service: FetcherService,
        worker: BackgroundWorker,
    ):
        self.repository = repository
        self.fetch_service = fetch_service
        self.worker = worker
        self._refetching: dict[str, asyncio.Future] = {}
        self._refetch_lock = asyncio.Lock()

    async def create_metadata(self, url: str):
        url = normalize_url(url)

        doc = await self.repository.get_or_create(url)

        if doc.status == FetchStatus.DONE:
            future = await self._dedup_refetch(url)
            if future is not None:
                return await future

        task = await self.worker.schedule_once(
            key=url,
            coro_factory=lambda u=url: self._fetch_and_store(u),
        )

        return await task

    async def _dedup_refetch(self, url: str) -> asyncio.Future | None:
        """
        Called when the URL is DONE.

        If another call is already handling the refetch, returns
        its Future so the caller can await it.

        Otherwise, creates a Future, registers it under *url*,
        resets the doc to PENDING, and returns None — the caller
        is responsible for running the fetch and resolving the
        Future on completion.
        """
        async with self._refetch_lock:
            existing = self._refetching.get(url)
            if existing is not None:
                return existing

            future = asyncio.get_running_loop().create_future()
            self._refetching[url] = future

        await self.repository.reset_to_pending(url)

        return None  # caller proceeds to schedule the fetch

    async def _resolve_refetch(self, url: str, result=None, exception=None):
        """Resolve the Future for *url* and clean up."""
        future = self._refetching.get(url)
        if future is None:
            return

        if exception is not None:
            future.set_exception(exception)
        elif result is not None:
            future.set_result(result)

        async with self._refetch_lock:
            if self._refetching.get(url) is future:
                del self._refetching[url]

    async def get_metadata(self, url: str):
        url = normalize_url(url)

        doc = await self.repository.get_by_url(url)

        if doc and doc.status == FetchStatus.DONE:
            return doc

        if not doc:
            await self.repository.get_or_create(url)

        elif doc.status == FetchStatus.ERROR:
            await self.repository.reset_to_pending(url)

        await self._trigger(url)

        return AcceptedResponse(
            url=url,
            status=FetchStatus.PENDING,
        )

    async def _fetch_and_store(self, url: str):
        try:
            await self.repository.update_status(url, FetchStatus.FETCHING)
            metadata = await self.fetch_service.fetch(url)
            result = await self.repository.update_metadata(url, metadata)
            await self._resolve_refetch(url, result=result)
            return result

        except Exception as e:
            await self.repository.update_error(url, str(e))
            await self._resolve_refetch(url, exception=e)
            logger.exception(f"Fetch failed for {url}: {e}")
            raise

    async def _trigger(self, url: str) -> None:
        """
        Schedule a background fetch for *url* if one isn't already
        running.  The returned task is deliberately not awaited
        (fire-and-forget).
        """
        await self.worker.schedule_once(
            key=url,
            coro_factory=lambda: self._fetch_and_store(url),
        )
