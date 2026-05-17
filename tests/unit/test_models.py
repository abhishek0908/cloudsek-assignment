import pytest
from datetime import datetime, timezone

from app.models.metadata import MetadataRecord, FetchStatus


class TestFetchStatus:

    def test_all_values_present(self):
        assert FetchStatus.PENDING.value == "pending"
        assert FetchStatus.FETCHING.value == "fetching"
        assert FetchStatus.DONE.value == "done"
        assert FetchStatus.ERROR.value == "error"
        assert len(FetchStatus) == 4


class TestMetadataRecord:

    def test_default_status_and_timestamps(self):
        record = MetadataRecord.model_construct(url="https://example.com")
        assert record.status == FetchStatus.PENDING
        assert isinstance(record.created_at, datetime)
        assert isinstance(record.updated_at, datetime)

    def test_can_set_custom_values(self):
        now = datetime.now(timezone.utc)
        record = MetadataRecord.model_construct(
            url="https://example.com",
            status=FetchStatus.DONE,
            status_code=200,
            headers={"content-type": "text/html"},
            page_source="<html>ok</html>",
            fetched_at=now,
        )
        assert record.status == FetchStatus.DONE
        assert record.status_code == 200

    def test_collection_name(self):
        assert MetadataRecord.Settings.name == "metadata"
