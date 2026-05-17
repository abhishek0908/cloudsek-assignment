from app.repositories.metadata import MetadataRepository
from app.services.fetcher import FetcherService
from app.workers.background_worker import BackgroundWorker
from app.services.metadata import MetadataService

_repository = MetadataRepository()
_fetch_service = FetcherService()
_worker = BackgroundWorker(limit=10)


def get_metadata_service() -> MetadataService:
    return MetadataService(
        repository=_repository,
        fetch_service=_fetch_service,
        worker=_worker,
    )