"""
AIClipper Publishing Routes

Endpoints for publishing clips to social platforms and fetching analytics.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db
from backend.api.schemas import (
    AnalyticsResponse,
    ErrorResponse,
    PublishRequest,
    PublishResponse,
)
from backend.database import crud
from backend.database.models import Platform
from backend.database.engine import get_session_context
from backend.utils.logging import get_logger

logger = get_logger("api.publishing")

router = APIRouter(tags=["Publishing"])

# Map of accepted platform strings to Platform enum values
_PLATFORM_MAP = {p.value: p for p in Platform}


@router.post(
    "/api/publish",
    response_model=PublishResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid platform"},
        404: {"model": ErrorResponse, "description": "Clip not found"},
    },
    summary="Publish a clip",
    description="Create a publish / upload job for a clip on the specified platform. "
    "Currently creates the Upload record in PENDING status; actual platform "
    "upload integration will be added later.",
)
async def publish_clip(
    body: PublishRequest,
    db: AsyncSession = Depends(get_db),
) -> PublishResponse:
    """Create an Upload record for a clip on a given platform."""
    # Validate platform
    platform_enum = _PLATFORM_MAP.get(body.platform.lower())
    if platform_enum is None:
        accepted = ", ".join(sorted(_PLATFORM_MAP))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform '{body.platform}'. Accepted: {accepted}",
        )

    # Verify the clip exists
    clip = await crud.get_clip(db, body.clip_id)
    if clip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clip with id {body.clip_id} not found.",
        )

    upload = await crud.create_upload(
        db,
        clip_id=body.clip_id,
        platform=platform_enum,
        scheduled_at=body.scheduled_at,
    )

    logger.info(
        f"Upload record created: id={upload.id}, clip={body.clip_id}, platform={body.platform}",
        extra={"clip_id": body.clip_id},
    )

    return PublishResponse.model_validate(upload)


async def _youtube_upload_task(upload_id: int, filepath: str, title: str, description: str, tags: list[str], privacy: str):
    try:
        from backend.services.uploaders.youtube import YouTubeUploader
        uploader = YouTubeUploader()
        uploader.authenticate()
        video_id = uploader.upload_video(filepath, title, description, tags, privacy)
        
        async with get_session_context() as session:
            upload = await crud.get_upload(session, upload_id)
            if upload:
                await crud.update_upload(session, upload_id, status="COMPLETED", platform_id=video_id)
    except Exception as e:
        logger.error(f"YouTube upload failed: {e}")
        async with get_session_context() as session:
            await crud.update_upload(session, upload_id, status="FAILED", error=str(e))


@router.post("/api/publish/batch/{video_id}")
async def batch_publish_to_youtube(
    video_id: int,
    privacy: str = Query(default="public"),
    db: AsyncSession = Depends(get_db),
):
    clips = await crud.get_clips_by_video(db, video_id)
    queued = 0
    
    youtube_platform = _PLATFORM_MAP.get("youtube", Platform.YOUTUBE)
    
    for clip in clips:
        if clip.status.value == "completed" and clip.output_path:
            title = clip.title or f"Clip {clip.clip_number}"
            description = clip.description or ""
            tags = clip.hashtags.split() if clip.hashtags else []
            
            upload = await crud.create_upload(
                db,
                clip_id=clip.id,
                platform=youtube_platform,
            )
            
            asyncio.create_task(
                _youtube_upload_task(
                    upload.id, 
                    str(clip.output_path), 
                    title, 
                    description, 
                    tags, 
                    privacy
                )
            )
            queued += 1

    return {"queued": queued, "message": f"Queued {queued} clips for YouTube upload."}


@router.get(
    "/api/analytics",
    response_model=AnalyticsResponse,
    summary="Dashboard analytics",
    description="Return aggregate statistics for the dashboard: total videos, clips, "
    "completed clips, published uploads, and projects.",
)
async def get_analytics(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsResponse:
    """Return dashboard-level aggregate stats."""
    stats = await crud.get_dashboard_stats(db)
    return AnalyticsResponse(**stats)


async def _upload_clip_to_youtube(clip_id: int, upload_id: int, title: str, description: str, tags: list[str], privacy: str, output_path: str):
    """Background task to upload a clip to YouTube."""
    from backend.services.uploaders.youtube import YouTubeUploader
    from backend.database.engine import get_session_context
    from backend.database.models import UploadStatus

    uploader = YouTubeUploader()
    try:
        # Assuming authenticate() uses default credentials
        await asyncio.to_thread(uploader.authenticate)
        
        # upload_video(file_path, title, description, tags, privacy_status)
        result = await asyncio.to_thread(
            uploader.upload_video,
            file_path=output_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy
        )
        
        async with get_session_context() as session:
            await crud.update_upload(
                session, 
                upload_id, 
                status=UploadStatus.PUBLISHED,
                url=result.get("url"),
                platform_video_id=result.get("video_id")
            )
    except Exception as e:
        logger.error(f"YouTube upload failed for clip {clip_id}: {e}")
        async with get_session_context() as session:
            await crud.update_upload(
                session, 
                upload_id, 
                status=UploadStatus.FAILED,
                error_message=str(e)
            )


from fastapi import Query
import asyncio
from backend.database.models import ClipStatus, Platform

@router.post("/api/publish/batch/{video_id}")
async def batch_publish_to_youtube(
    video_id: int,
    privacy: str = Query(default="public"),
    db: AsyncSession = Depends(get_db),
):
    """Batch publish all completed clips for a video to YouTube."""
    clips = await crud.list_clips(db, video_id=video_id, status=ClipStatus.COMPLETED)
    queued_count = 0
    
    for clip in clips:
        if not clip.output_path:
            continue
            
        title = clip.title or f"Clip {clip.id}"
        description = clip.description or ""
        hashtags = clip.hashtags or ""
        tags = [t.strip().strip('#') for t in hashtags.split()] if hashtags else []
        
        upload = await crud.create_upload(
            db,
            clip_id=clip.id,
            platform=Platform.YOUTUBE,
        )
        
        asyncio.create_task(
            _upload_clip_to_youtube(
                clip_id=clip.id,
                upload_id=upload.id,
                title=title,
                description=description,
                tags=tags,
                privacy=privacy,
                output_path=clip.output_path
            )
        )
        queued_count += 1
        
    return {"queued_clips": queued_count}
