from datetime import datetime,UTC
from enum import Enum
from typing import Annotated, Optional

from beanie import Document, Indexed
from pydantic import Field


class FetchStatus(str, Enum):
    PENDING = "pending"
    FETCHING = "fetching"
    DONE = "done"
    ERROR = "error"


class MetadataRecord(Document):

    url: Annotated[str, Indexed(unique=True)]

    status: FetchStatus = FetchStatus.PENDING

    headers: dict[str, str] = Field(
        default_factory=dict
    )

    cookies: dict[str, str] = Field(
        default_factory=dict
    )

    page_source: Optional[str] = None

    status_code: Optional[int] = None

    error_message: Optional[str] = None

    fetched_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "metadata"