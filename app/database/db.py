from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pymongo.errors import PyMongoError

from app.core.logger import get_logger

logger = get_logger(__name__)

client: AsyncIOMotorClient | None = None


async def connect_db(mongo_url: str) -> None:
    global client

    try:
        client = AsyncIOMotorClient(
            mongo_url,
            maxPoolSize=20,
            minPoolSize=5,
            serverSelectionTimeoutMS=5000,
        )

        await client.admin.command("ping")

        # Beanie 2.1.0 internally calls client.append_metadata();
        # Motor 3.7+ __getattr__ intercepts unknown attrs, so we
        # stub it directly on the instance to bypass the fallback.
        client.append_metadata = lambda _: None

        logger.info("Connected to MongoDB")

    except PyMongoError as e:
        logger.exception(f"MongoDB connection failed url={mongo_url} error={e}")
        raise


async def close_db() -> None:
    global client

    if client:
        client.close()
        client = None
        logger.info("MongoDB connection closed")

