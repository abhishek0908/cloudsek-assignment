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

        logger.info("Connected to MongoDB")

    except PyMongoError as e:
        logger.exception(f"MongoDB connection failed: {e}")
        raise


async def close_db() -> None:
    global client

    if client:
        client.close()
        client = None
        logger.info("MongoDB connection closed")


def get_collection(
    db_name: str,
    collection_name: str,
) -> AsyncIOMotorCollection:

    if client is None:
        raise RuntimeError(
            "Database not connected. Call connect_db() first."
        )

    return client[db_name][collection_name]