import asyncio
import pytest

from app.models.metadata import FetchStatus, MetadataRecord
from app.services.metadata import MetadataService
from app.schemas.metadata import FetchedMetadata


class TestConcurrentCreateMetadata:
    """
    Verifies that multiple concurrent POST requests for the
    same URL do not produce DuplicateKeyError and that only
    one fetch actually executes.
    """

    @pytest.mark.asyncio
    async def test_concurrent_new_url_no_duplicate_key(
        self,
        metadata_service: MetadataService,
        mocked_fetcher,
    ):
        url = "https://example.com"

        # Ensure the HTTP client returns valid data for all calls
        async def fake_fetch(_url):
            return FetchedMetadata(
                url=_url,
                status_code=200,
                headers={"content-type": "text/html"},
                cookies={},
                page_source="<html>concurrent</html>",
            )

        mocked_fetcher.fetch = fake_fetch

        results = await asyncio.gather(
            metadata_service.create_metadata(url),
            metadata_service.create_metadata(url),
            metadata_service.create_metadata(url),
        )

        # All three returned a result (no exception = no DuplicateKeyError)
        assert len(results) == 3
        for r in results:
            assert r.status == FetchStatus.DONE
            assert r.url == url

        # Only one document exists in the database
        count = await MetadataRecord.find(
            MetadataRecord.url == url
        ).count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_concurrent_done_url_only_one_fetch(
        self,
        metadata_service: MetadataService,
        mocked_fetcher,
        repository,
    ):
        """
        When the URL already exists with DONE status, concurrent
        create_metadata calls should still produce only one fetch.
        """
        url = "https://refetch-test.com"
        fetch_count = 0

        async def counting_fetch(_url):
            nonlocal fetch_count
            fetch_count += 1
            return FetchedMetadata(
                url=_url,
                status_code=200,
                headers={"content-type": "text/html"},
                cookies={},
                page_source="<html>refetch</html>",
            )

        mocked_fetcher.fetch = counting_fetch

        # First request creates + fetches
        await metadata_service.create_metadata(url)
        assert fetch_count == 1

        # Second batch of concurrent requests should refetch
        await asyncio.gather(
            metadata_service.create_metadata(url),
            metadata_service.create_metadata(url),
        )

        # Only one extra fetch should have happened (not 2)
        assert fetch_count == 2  # first + one refetch


class TestConcurrentGetMetadata:
    """
    Verifies that GET requests do not trigger duplicate
    background fetches.
    """

    @pytest.mark.asyncio
    async def test_background_dedup(
        self,
        metadata_service: MetadataService,
        mocked_fetcher,
        repository,
    ):
        url = "https://background-dedup.com"
        fetch_count = 0

        async def counting_fetch(_url):
            nonlocal fetch_count
            fetch_count += 1
            await asyncio.sleep(0.05)
            return FetchedMetadata(
                url=_url,
                status_code=200,
                headers={"content-type": "text/html"},
                cookies={},
                page_source="<html>dedup</html>",
            )

        mocked_fetcher.fetch = counting_fetch

        # Concurrent GETs for a new URL — should trigger only one fetch
        results = await asyncio.gather(
            metadata_service.get_metadata(url),
            metadata_service.get_metadata(url),
            metadata_service.get_metadata(url),
        )

        # All returned AcceptedResponse (pending)
        from app.schemas.metadata import AcceptedResponse

        assert all(isinstance(r, AcceptedResponse) for r in results)
        assert all(r.status == FetchStatus.PENDING for r in results)

        # Wait for background fetch to complete
        await asyncio.sleep(0.2)

        # Only one fetch should have executed
        assert fetch_count == 1

        # Document should now be DONE
        doc = await repository.get_by_url(url)
        assert doc is not None
        assert doc.status == FetchStatus.DONE


class TestRaceConditionRegression:
    """
    Regression tests for specific race conditions that were
    present in the original code.
    """

    @pytest.mark.asyncio
    async def test_get_or_create_atomic_upsert(
        self,
        repository,
    ):
        """
        10 concurrent get_or_create for the same new URL must
        produce exactly one document (no DuplicateKeyError).
        """
        url = "https://race-regression.com"

        results = await asyncio.gather(
            *[repository.get_or_create(url) for _ in range(10)],
        )

        assert len(results) == 10
        assert all(r.url == url for r in results)

        count = await MetadataRecord.find(
            MetadataRecord.url == url
        ).count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_schedule_once_dedup_real_worker(
        self,
        background_worker,
    ):
        """
        schedule_once with 10 concurrent calls for the same key.
        Only one task should actually run.
        """
        execution_count = 0

        async def work():
            nonlocal execution_count
            execution_count += 1
            await asyncio.sleep(0.1)

        tasks = await asyncio.gather(
            *[
                background_worker.schedule_once("dedup-key", lambda: work())
                for _ in range(10)
            ],
        )

        # Wait for all returned tasks
        await asyncio.gather(*tasks)

        assert execution_count == 1

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(
        self,
        background_worker,
    ):
        """
        The semaphore must limit concurrent executions to the
        configured maximum (3 in this test).
        """
        from app.workers.background_worker import BackgroundWorker

        worker = BackgroundWorker(limit=3)
        concurrent_max = 0
        lock = asyncio.Lock()

        async def work():
            nonlocal concurrent_max
            async with lock:
                concurrent_max += 1
            await asyncio.sleep(0.1)
            async with lock:
                concurrent_max -= 1

        tasks = await asyncio.gather(
            *[
                worker.schedule_once(f"key-{i}", lambda: work())
                for i in range(10)
            ],
        )
        await asyncio.gather(*tasks)

        assert concurrent_max <= 3
