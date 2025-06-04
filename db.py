import aiosqlite
from contextlib import asynccontextmanager

DB_PATH = "settings.db"

_db = None

async def get_db():
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
    return _db

@asynccontextmanager
async def connection():
    db = await get_db()
    try:
        yield db
    finally:
        pass

async def close_db():
    global _db
    if _db is not None:
        await _db.close()
        _db = None
