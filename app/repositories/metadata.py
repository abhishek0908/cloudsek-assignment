from datetime import datetime, timezone

from beanie.odm.queries.update import UpdateResponse
from beanie.operators import In
from app.models.metadata import (
    MetadataRecord,
    FetchStatus,
)
from app.schemas.metadata import (
    FetchedMetadata,
    MetadataResponse,
)
from app.core.logger import get_logger
logger = get_logger(__name__)


class MetadataRepository:

    async def get_by_url(
        self,
        url: str,
    ):
        return await MetadataRecord.find_one(
            MetadataRecord.url == url,
        )

    async def get_or_create(
        self,
        url: str,
    ) -> MetadataRecord:
        """
        Atomically return the existing document for *url* or
        create a new one with status PENDING.

        Uses pymongo's find_one_and_update with upsert=True
        so that two concurrent calls for the same new URL
        cannot produce a DuplicateKeyError.
        """

        now = datetime.now(timezone.utc)

        doc = await MetadataRecord.find_one(
            MetadataRecord.url == url,
        ).upsert(
            {
                "$setOnInsert": {
                    "headers": {},
                    "cookies": {},
                    "page_source": None,
                    "status_code": None,
                    "error_message": None,
                    "fetched_at": None,
                    "created_at": now,
                    "updated_at": now,
                }
            },
            on_insert=MetadataRecord(
                url=url,
                status=FetchStatus.PENDING,
            ),
            response_type=UpdateResponse.NEW_DOCUMENT,
            upsert=True,
        )

        return doc

    async def reset_to_pending(
        self,
        url: str,
    ) -> MetadataRecord | None:
        """
        Atomically set status to PENDING — only if the document
        currently has status DONE.

        Returns the updated document or None if the document does
        not exist or its status is not DONE.
        """

        now = datetime.now(timezone.utc)

        doc = await MetadataRecord.find_one(
            MetadataRecord.url == url,
            In(MetadataRecord.status, [FetchStatus.DONE, FetchStatus.ERROR]),
        ).update(
            {
                "$set": {
                    "status": FetchStatus.PENDING,
                    "updated_at": now,
                }
            },
            response_type=UpdateResponse.NEW_DOCUMENT,
        )

        return doc

    async def update_status(
        self,
        url: str,
        status: FetchStatus,
    ):
        """
        Atomically update the status and updated_at timestamp.
        """

        now = datetime.now(timezone.utc)

        await MetadataRecord.find_one(
            MetadataRecord.url == url,
        ).update(
            {
                "$set": {
                    "status": status,
                    "updated_at": now,
                }
            },
        )

    async def update_metadata(
        self,
        url: str,
        metadata: FetchedMetadata,
    ) -> MetadataResponse:

        now = datetime.now(timezone.utc)

        doc = await MetadataRecord.find_one(
            MetadataRecord.url == url,
        ).update(
            {
                "$set": {
                    "status": FetchStatus.DONE,
                    "status_code": metadata.status_code,
                    "headers": metadata.headers,
                    "cookies": metadata.cookies,
                    "page_source": metadata.page_source,
                    "error_message": None,
                    "fetched_at": now,
                    "updated_at": now,
                }
            },
            response_type=UpdateResponse.NEW_DOCUMENT,
        )

        return MetadataResponse.model_validate(
            doc,
            from_attributes=True,
        )

    async def update_error(
        self,
        url: str,
        error_message: str,
    ) -> None:

        now = datetime.now(timezone.utc)

        await MetadataRecord.find_one(
            MetadataRecord.url == url,
        ).update(
            {
                "$set": {
                    "status": FetchStatus.ERROR,
                    "error_message": error_message,
                    "updated_at": now,
                }
            },
        )
