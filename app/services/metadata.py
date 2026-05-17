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

    async def create_metadata(self, url: str):
        url = normalize_url(url)

        doc = await self.repository.get_or_create(url)

        if doc.status == FetchStatus.DONE:
            await self.repository.reset_to_pending(url)

        task = await self.worker.schedule_once(
            key=url,
            coro_factory=lambda u=url: self._fetch_and_store(u),
        )

        return await task

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
            return await self.repository.update_metadata(url, metadata)

        except Exception as e:
            await self.repository.update_error(url, str(e))
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
