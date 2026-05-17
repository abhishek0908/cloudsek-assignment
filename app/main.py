from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api.routes import api_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.exception_handlers import (
    app_error_handler,
    validation_exception_handler,
    generic_exception_handler,
)
from app.core.logger import get_logger,configure_logging
from app.database import init_database
from app.database.db import (
    close_db,
    connect_db,
)
logger = get_logger(__name__)


configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Application is starting...")

    await connect_db(settings.mongodb_url)
    await init_database()

    yield

    logger.info("Application is shutting down...")

    await close_db()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(
    api_router,
    prefix="/api/v1",
)

app.add_exception_handler(
    AppError,
    app_error_handler,
)

app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,
)

app.add_exception_handler(
    Exception,
    generic_exception_handler,
)