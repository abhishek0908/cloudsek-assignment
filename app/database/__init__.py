from beanie import init_beanie

from app.core.config import settings
from app.database import db
from app.models.metadata import MetadataRecord


async def init_database():
    await init_beanie(
        database=db.client[settings.database_name],
        document_models=[
            MetadataRecord,
        ],
    )