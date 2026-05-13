from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.logger import get_logger
from app.api.routes import api_router
from app.database.db import (
    connect_db,
    close_db,
    get_collection,
)
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application is starting...")
    await connect_db(settings.mongodb_url)
    yield

    logger.info("Application is shutting down...")
    await close_db()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan
)

app.include_router(api_router)

@app.get("/")
def root():
    """
    Root endpoint
    """

    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }