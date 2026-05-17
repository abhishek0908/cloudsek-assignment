import asyncio
import pytest
from unittest.mock import AsyncMock, Mock

from app.services.metadata import MetadataService
from app.models.metadata import FetchStatus
from app.schemas.metadata import FetchedMetadata, AcceptedResponse


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
def mock_fetcher():
    return AsyncMock()


@pytest.fixture
def mock_worker():
    m = AsyncMock()

    async def schedule_once_side_effect(key, coro_factory):
        coro = coro_factory()
        return asyncio.create_task(coro)

    m.schedule_once = AsyncMock(side_effect=schedule_once_side_effect)
    return m


@pytest.fixture
def metadata_service(mock_repo, mock_fetcher, mock_worker):
    return MetadataService(
        repository=mock_repo,
        fetch_service=mock_fetcher,
        worker=mock_worker,
    )


def _existing_record(status=FetchStatus.DONE):
    r = Mock(status=status)
    r.model_dump.return_value = {
        "url": "https://example.com/",
        "status": status.value,
    }
    return r


def _fetched_metadata(url="https://example.com/"):
    return FetchedMetadata(
        url=url,
        status_code=200,
        headers={"content-type": "text/html"},
        cookies={},
        page_source="<html>ok</html>",
    )


class TestCreateMetadata:

    @pytest.mark.asyncio
    async def test_new_url_creates_then_fetches(
        self,
        metadata_service,
        mock_repo,
        mock_fetcher,
    ):
        url = "https://example.com/"
        mock_repo.get_or_create.return_value = _existing_record(
            FetchStatus.PENDING,
        )
        mock_fetcher.fetch.return_value = _fetched_metadata()
        mock_repo.update_metadata.return_value = {
            "id": "x",
            "status": FetchStatus.DONE,
        }

        result = await metadata_service.create_metadata(url)

        mock_repo.get_or_create.assert_called_once_with(url)
        mock_repo.reset_to_pending.assert_not_called()
        mock_repo.update_status.assert_called_once_with(
            url,
            FetchStatus.FETCHING,
        )
        mock_fetcher.fetch.assert_called_once_with(url)
        assert result == {"id": "x", "status": FetchStatus.DONE}

    @pytest.mark.asyncio
    async def test_existing_done_resets_then_refetches(
        self,
        metadata_service,
        mock_repo,
        mock_fetcher,
    ):
        url = "https://example.com/"
        mock_repo.get_or_create.return_value = _existing_record(
            FetchStatus.DONE,
        )
        mock_fetcher.fetch.return_value = _fetched_metadata()
        mock_repo.update_metadata.return_value = {"status": FetchStatus.DONE}

        result = await metadata_service.create_metadata(url)

        mock_repo.reset_to_pending.assert_called_once_with(url)
        mock_repo.update_status.assert_called_once_with(
            url,
            FetchStatus.FETCHING,
        )
        assert result["status"] == FetchStatus.DONE

    @pytest.mark.asyncio
    async def test_existing_pending_fetches_without_creating(
        self,
        metadata_service,
        mock_repo,
        mock_fetcher,
    ):
        url = "https://example.com/"
        mock_repo.get_or_create.return_value = _existing_record(
            FetchStatus.PENDING,
        )
        mock_fetcher.fetch.return_value = _fetched_metadata()
        mock_repo.update_metadata.return_value = {"status": FetchStatus.DONE}

        result = await metadata_service.create_metadata(url)

        mock_repo.reset_to_pending.assert_not_called()
        mock_repo.update_status.assert_called_once_with(
            url,
            FetchStatus.FETCHING,
        )
        assert result["status"] == FetchStatus.DONE

    @pytest.mark.asyncio
    async def test_existing_error_fetches_without_reset(
        self,
        metadata_service,
        mock_repo,
        mock_fetcher,
    ):
        url = "https://example.com/"
        mock_repo.get_or_create.return_value = _existing_record(
            FetchStatus.ERROR,
        )
        mock_fetcher.fetch.return_value = _fetched_metadata()
        mock_repo.update_metadata.return_value = {"status": FetchStatus.DONE}

        result = await metadata_service.create_metadata(url)

        mock_repo.get_or_create.assert_called_once_with(url)
        mock_repo.reset_to_pending.assert_not_called()
        mock_repo.update_status.assert_called_once_with(
            url,
            FetchStatus.FETCHING,
        )
        assert result["status"] == FetchStatus.DONE

    @pytest.mark.asyncio
    async def test_fetch_failure_records_error_and_reraises(
        self,
        metadata_service,
        mock_repo,
        mock_fetcher,
    ):
        url = "https://example.com/"
        mock_repo.get_or_create.return_value = _existing_record(
            FetchStatus.PENDING,
        )
        mock_fetcher.fetch.side_effect = RuntimeError("connection lost")

        with pytest.raises(RuntimeError, match="connection lost"):
            await metadata_service.create_metadata(url)

        mock_repo.update_error.assert_called_once_with(url, "connection lost")


class TestGetMetadata:

    @pytest.mark.asyncio
    async def test_returns_done_document_immediately(
        self,
        metadata_service,
        mock_repo,
        mock_worker,
    ):
        url = "https://example.com/"
        record = _existing_record(FetchStatus.DONE)
        mock_repo.get_by_url.return_value = record

        result = await metadata_service.get_metadata(url)

        assert result == record
        mock_worker.schedule_once.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_url_creates_and_triggers_background(
        self,
        metadata_service,
        mock_repo,
        mock_worker,
    ):
        url = "https://example.com/"
        mock_repo.get_by_url.return_value = None
        mock_repo.get_or_create.return_value = _existing_record(
            FetchStatus.PENDING,
        )

        result = await metadata_service.get_metadata(url)

        mock_repo.get_or_create.assert_called_once_with(url)
        mock_worker.schedule_once.assert_called_once()
        assert mock_worker.schedule_once.call_args[1]["key"] == url
        assert isinstance(result, AcceptedResponse)
        assert result.status == FetchStatus.PENDING

    @pytest.mark.asyncio
    async def test_error_url_resets_and_triggers_background(
        self,
        metadata_service,
        mock_repo,
        mock_worker,
    ):
        url = "https://example.com/"
        mock_repo.get_by_url.return_value = _existing_record(
            FetchStatus.ERROR,
        )

        result = await metadata_service.get_metadata(url)

        mock_repo.reset_to_pending.assert_called_once_with(url)
        mock_worker.schedule_once.assert_called_once()
        assert mock_worker.schedule_once.call_args[1]["key"] == url
        assert isinstance(result, AcceptedResponse)

    @pytest.mark.asyncio
    async def test_pending_url_returns_accepted_no_duplicate_trigger(
        self,
        metadata_service,
        mock_repo,
        mock_worker,
    ):
        url = "https://example.com/"
        mock_repo.get_by_url.return_value = _existing_record(
            FetchStatus.PENDING,
        )

        result = await metadata_service.get_metadata(url)

        mock_repo.get_or_create.assert_not_called()
        mock_repo.reset_to_pending.assert_not_called()
        mock_worker.schedule_once.assert_called_once()
        assert isinstance(result, AcceptedResponse)

    @pytest.mark.asyncio
    async def test_fetching_url_returns_accepted_no_duplicate_trigger(
        self,
        metadata_service,
        mock_repo,
        mock_worker,
    ):
        url = "https://example.com/"
        mock_repo.get_by_url.return_value = _existing_record(
            FetchStatus.FETCHING,
        )

        result = await metadata_service.get_metadata(url)

        mock_repo.get_or_create.assert_not_called()
        mock_repo.reset_to_pending.assert_not_called()
        mock_worker.schedule_once.assert_called_once()
        assert isinstance(result, AcceptedResponse)
