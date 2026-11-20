import logging
import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING
from config import settings

logger = logging.getLogger("auth_service.db")


class Database:
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None


db_state = Database()


async def connect_to_database():
    logger.info("Connecting Auth Service to MongoDB...")
    db_state.client = AsyncIOMotorClient(
        settings.MONGODB_URI,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000,
        maxPoolSize=25,
        minPoolSize=2
    )
    await db_state.client.admin.command("ping")
    db_state.db = db_state.client.get_default_database()
    logger.info(f"Auth Service connected to database: {db_state.db.name}")

    try:
        users = get_users_collection()
        await users.create_index([("email", ASCENDING)], unique=True)
    except Exception as e:
        logger.warning(f"Could not verify users index: {e}")


async def close_database_connection():
    if db_state.client:
        db_state.client.close()
        logger.info("Auth Service database connection closed.")


def get_users_collection():
    if db_state.db is None:
        raise RuntimeError("Database not initialized.")
    return db_state.db["users"]
