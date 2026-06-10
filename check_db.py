import asyncio
from pathlib import Path
from backend.database.engine import init_db, get_session_context
from backend.database import crud

async def main():
    await init_db()
    async with get_session_context() as s:
        v = await crud.get_video(s, 1)
        print(f"filepath: {v.filepath}")
        p = Path(v.filepath)
        print(f"exists: {p.exists()}")
        print(f"absolute: {p.absolute()}")

asyncio.run(main())
