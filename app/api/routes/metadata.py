from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from pydantic import AnyHttpUrl

from app.schemas.metadata import (
    CreateMetadataRequest,
    MetadataResponse,
)

from app.core.responses import success_response

from app.services.metadata import (
    MetadataService,
)

from app.dependencies import (
    get_metadata_service,
)

from app.models.metadata import FetchStatus

router = APIRouter(
    prefix="/metadata",
    tags=["Metadata"],
)


@router.post("/", response_model=MetadataResponse)
async def create_metadata(
    request: CreateMetadataRequest,

    metadata_service: MetadataService = Depends(
        get_metadata_service
    ),
):

    data = await metadata_service.create_metadata(
        str(request.url)
    )
    return success_response(
        message="Metadata processing completed",
        data=data,
        status_code=201,
    )


@router.get("/")
async def get_metadata(
    url: AnyHttpUrl = Query(
        ...,
        description="The URL to fetch metadata for",
    ),
    metadata_service: MetadataService = Depends(
        get_metadata_service
    ),
):

    data = await metadata_service.get_metadata(
        str(url),
    )

    # Return 200 when data is immediately available,
    # 202 when a background fetch has been scheduled
    is_done = (
        isinstance(data, dict) and data.get("status") == FetchStatus.DONE
    ) or (
        hasattr(data, "status") and data.status == FetchStatus.DONE
    )

    status_code = 200 if is_done else 202

    message = (
        "Metadata fetched successfully"
        if status_code == 200
        else "Metadata not found, fetch has been scheduled"
    )

    return success_response(
        message=message,
        data=data,
        status_code=status_code,
    )
