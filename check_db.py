"""Reset video for re-processing with new pipeline."""
import asyncio
from pathlib import Path
from backend.database.engine import init_db, get_session_context
from backend.database import crud
from backend.database.models import VideoStatus, Clip, Subtitle, Thumbnail
from sqlalchemy import delete

async def main():
    await init_db()
    async with get_session_context() as s:
        # Delete old clips and their files
        clips = await crud.list_clips(s, video_id=1)
        for c in clips:
            if c.output_path:
                p = Path(c.output_path)
                if p.exists():
                    p.unlink()
                    print(f"  Deleted: {p}")

        await s.execute(delete(Subtitle))
        await s.execute(delete(Thumbnail))
        await s.execute(delete(Clip).where(Clip.video_id == 1))
        await crud.update_video_status(s, 1, status=VideoStatus.PENDING, progress=0, step=None, error=None)
        print("Video 1 reset to PENDING. Ready for new pipeline.")

asyncio.run(main())
