from typing import Any, Generic, Optional, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None
    error: Optional[dict[str, Any]] = None
    meta: Optional[dict[str, Any]] = None


def success_response(
    message: str = "Request successful",
    data: Any = None,
    status_code: int = 200,
    meta: dict[str, Any] | None = None,
) -> JSONResponse:

    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")

    response = ApiResponse(
        success=True,
        message=message,
        data=data,
        meta=meta,
    )

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(mode="json"),
    )


def error_response(
    error_code: str,
    message: str,
    status_code: int = 400,
    details: Any = None,
) -> JSONResponse:

    error_payload = {
        "code": error_code,
    }

    if details is not None:
        error_payload["details"] = details

    response = ApiResponse(
        success=False,
        message=message,
        error=error_payload,
    )

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(mode="json"),
    )