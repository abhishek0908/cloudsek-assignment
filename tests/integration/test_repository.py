import asyncio
import pytest
from datetime import datetime, timezone

from app.models.metadata import FetchStatus, MetadataRecord
from app.schemas.metadata import FetchedMetadata


class TestGetOrCreate:

    @pytest.mark.asyncio
    async def test_creates_new_document(self, repository):
        url = "https://example.com"
        doc = await repository.get_or_create(url)

        assert doc.url == url
        assert doc.status == FetchStatus.PENDING
        assert doc.headers == {}
        assert doc.cookies == {}
        assert doc.page_source is None
        assert doc.status_code is None
        assert doc.error_message is None

    @pytest.mark.asyncio
    async def test_returns_existing_document(self, repository):
        url = "https://example.com"
        first = await repository.get_or_create(url)
        second = await repository.get_or_create(url)

        # Same document (same _id), not a duplicate
        assert first.id == second.id
        assert second.status == FetchStatus.PENDING

    @pytest.mark.asyncio
    async def test_does_not_overwrite_status(self, repository):
        url = "https://example.com"
        await repository.get_or_create(url)

        # Manually advance status to FETCHING
        doc = await MetadataRecord.find_one(MetadataRecord.url == url)
        doc.status = FetchStatus.FETCHING
        await doc.save()

        # get_or_create should return the existing doc WITHOUT resetting
        refetched = await repository.get_or_create(url)
        assert refetched.status == FetchStatus.FETCHING

    @pytest.mark.asyncio
    async def test_concurrent_no_duplicate_key(self, repository):
        """
        Two concurrent get_or_create calls for the same new URL
        must NOT produce a DuplicateKeyError.
        """
        url = "https://concurrent-test.com"

        async def create():
            return await repository.get_or_create(url)

        results = await asyncio.gather(create(), create(), create())

        ids = {r.id for r in results if r is not None}
        assert len(ids) == 1  # all returned the same document

    @pytest.mark.asyncio
    async def test_multiple_urls(self, repository):
        urls = [
            "https://alpha.com",
            "https://beta.com",
            "https://gamma.com",
        ]
        docs = await asyncio.gather(
            *(repository.get_or_create(u) for u in urls)
        )
        assert len({d.url for d in docs}) == 3
        assert all(d.status == FetchStatus.PENDING for d in docs)


class TestResetToPending:

    @pytest.mark.asyncio
    async def test_resets_done_to_pending(self, repository):
        url = "https://example.com"
        await repository.get_or_create(url)

        # Set status to DONE
        doc = await MetadataRecord.find_one(MetadataRecord.url == url)
        doc.status = FetchStatus.DONE
        doc.fetched_at = datetime.now(timezone.utc)
        await doc.save()

        result = await repository.reset_to_pending(url)
        assert result is not None
        assert result.status == FetchStatus.PENDING
    @pytest.mark.asyncio
    async def test_does_not_reset_pending(self, repository):
        url = "https://example.com"
        await repository.get_or_create(url)

        result = await repository.reset_to_pending(url)
        assert result is None  # status is PENDING, not DONE

    @pytest.mark.asyncio
    async def test_resets_error_to_pending(
        self,
        repository,
    ):
        url = "https://example.com"

        doc = await repository.get_or_create(url)

        doc.status = FetchStatus.ERROR
        doc.error_message = "oops"

        await doc.save()

        result = await repository.reset_to_pending(url)

        assert result is not None
        assert result.status == FetchStatus.PENDING

        updated = await repository.get_by_url(url)

        assert updated.status == FetchStatus.PENDING

    @pytest.mark.asyncio
    async def test_does_not_reset_fetching(self, repository):
        url = "https://example.com"
        doc = await repository.get_or_create(url)
        doc.status = FetchStatus.FETCHING
        await doc.save()

        result = await repository.reset_to_pending(url)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_url(self, repository):
        result = await repository.reset_to_pending(
            "https://nonexistent.com",
        )
        assert result is None


class TestUpdateStatus:

    @pytest.mark.asyncio
    async def test_updates_status(self, repository):
        url = "https://example.com"
        await repository.get_or_create(url)

        await repository.update_status(url, FetchStatus.FETCHING)

        doc = await MetadataRecord.find_one(MetadataRecord.url == url)
        assert doc.status == FetchStatus.FETCHING
        assert doc.updated_at is not None

    @pytest.mark.asyncio
    async def test_updates_multiple_times(self, repository):
        url = "https://example.com"
        await repository.get_or_create(url)

        for status in [
            FetchStatus.FETCHING,
            FetchStatus.DONE,
            FetchStatus.PENDING,
        ]:
            await repository.update_status(url, status)

        doc = await MetadataRecord.find_one(MetadataRecord.url == url)
        assert doc.status == FetchStatus.PENDING

    @pytest.mark.asyncio
    async def test_does_not_crash_on_missing_url(self, repository):
        await repository.update_status(
            "https://nonexistent.com",
            FetchStatus.FETCHING,
        )


class TestUpdateMetadata:

    @pytest.mark.asyncio
    async def test_stores_full_metadata(self, repository):
        url = "https://example.com"
        await repository.get_or_create(url)

        metadata = FetchedMetadata(
            url=url,
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            cookies={"session": "abc123"},
            page_source="<html>Hello</html>",
        )

        response = await repository.update_metadata(url, metadata)

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert response.cookies["session"] == "abc123"
        assert response.page_source == "<html>Hello</html>"
        assert response.status == FetchStatus.DONE
        assert response.error_message is None
        assert response.fetched_at is not None

    @pytest.mark.asyncio
    async def test_updates_existing_metadata(self, repository):
        url = "https://example.com"
        await repository.get_or_create(url)

        first = FetchedMetadata(
            url=url,
            status_code=200,
            headers={},
            cookies={},
            page_source="first",
        )
        second = FetchedMetadata(
            url=url,
            status_code=404,
            headers={"x-custom": "val"},
            cookies={},
            page_source="second",
        )

        await repository.update_metadata(url, first)
        response = await repository.update_metadata(url, second)

        assert response.status_code == 404
        assert response.page_source == "second"
        assert response.headers["x-custom"] == "val"


class TestUpdateError:

    @pytest.mark.asyncio
    async def test_sets_error_status(self, repository):
        url = "https://example.com"
        await repository.get_or_create(url)

        await repository.update_error(url, "connection refused")

        doc = await MetadataRecord.find_one(MetadataRecord.url == url)
        assert doc.status == FetchStatus.ERROR
        assert doc.error_message == "connection refused"

    @pytest.mark.asyncio
    async def test_does_not_crash_on_missing_url(self, repository):
        await repository.update_error(
            "https://nonexistent.com",
            "something broke",
        )
