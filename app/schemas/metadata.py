from datetime import datetime
from pydantic import AnyHttpUrl, BaseModel
from app.models.metadata import FetchStatus


class CreateMetadataRequest(BaseModel):
    url: AnyHttpUrl


class MetadataResponse(BaseModel):
    url: str
    status: FetchStatus
    status_code: int | None = None
    headers: dict[str, str] = {}
    cookies: dict[str, str] = {}
    page_source: str | None = None
    error_message: str | None = None
    fetched_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AcceptedResponse(BaseModel):
    message: str
    url: str
    status: FetchStatus = FetchStatus.PENDING




class FetchedMetadata(BaseModel):
    url: str
    status_code: int
    headers: dict[str, str]
    cookies: dict[str, str]
    page_source: str


