import aiosqlite
import logging
from contextlib import asynccontextmanager

DB_PATH = "settings.db"

_db = None

logger = logging.getLogger(__name__)

async def get_db():
    global _db
    if _db is None:
        logger.info("Opening database connection")
        _db = await aiosqlite.connect(DB_PATH)
    return _db

@asynccontextmanager
async def connection():
    logger.info("Using database connection")
    db = await get_db()
    try:
        yield db
    finally:
        pass

async def close_db():
    global _db
    if _db is not None:
        logger.info("Closing database connection")
        await _db.close()
        _db = None
