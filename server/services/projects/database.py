import logging
import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from config import settings

logger = logging.getLogger("project_service.db")


class Database:
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None


db_state = Database()


async def connect_to_database():
    logger.info("Connecting Project Service to MongoDB...")
    db_state.client = AsyncIOMotorClient(
        settings.MONGODB_URI,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000,
        maxPoolSize=25,
        minPoolSize=2
    )
    await db_state.client.admin.command("ping")
    db_state.db = db_state.client.get_default_database()
    logger.info(f"Project Service connected to database: {db_state.db.name}")

    try:
        projects = get_projects_collection()
        await projects.create_index([("user", ASCENDING)])
        await projects.create_index([("updatedAt", DESCENDING)])
    except Exception as e:
        logger.warning(f"Could not verify projects index: {e}")


async def close_database_connection():
    if db_state.client:
        db_state.client.close()
        logger.info("Project Service database connection closed.")


def get_projects_collection():
    if db_state.db is None:
        raise RuntimeError("Database not initialized.")
    return db_state.db["projects"]
