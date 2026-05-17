from fastapi import Request
from fastapi.exceptions import RequestValidationError

from app.core.exceptions import AppError
from app.core.responses import error_response


async def app_error_handler(
    request: Request,
    exc: AppError,
):

    return error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):

    return error_response(
        error_code="VALIDATION_ERROR",
        message="Invalid request payload",
        status_code=422,
        details=exc.errors(),
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
):

    return error_response(
        error_code="INTERNAL_SERVER_ERROR",
        message="Something went wrong",
        status_code=500,
    )