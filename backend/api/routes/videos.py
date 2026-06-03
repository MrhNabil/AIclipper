"""
AIClipper Video Routes

Endpoints for uploading, listing, and retrieving video details.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_config, get_current_user, get_db
from backend.api.schemas import (
    ErrorResponse,
    VideoDetail,
    VideoListItem,
    VideoListResponse,
    VideoUploadResponse,
)
from backend.database import crud
from backend.database.models import User, Video
from backend.utils.config import Settings
from backend.utils.logging import get_logger
from backend.utils.validators import ValidationError, validate_video_file

logger = get_logger("api.videos")

router = APIRouter(tags=["Videos"])


@router.post(
    "/api/upload",
    response_model=VideoUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Upload a video file",
    description="Upload a video file for processing. The file is validated for format, size, "
    "and integrity before being saved.",
)
async def upload_video(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    config: Settings = Depends(get_config),
) -> VideoUploadResponse:
    """Accept a video upload, validate it, save to disk, and create a DB record."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided.",
        )

    # Generate a unique filename to prevent collisions
    original_name = file.filename
    ext = Path(original_name).suffix.lower()
    safe_name = f"{uuid.uuid4().hex}{ext}"
    save_path = config.upload_dir / safe_name

    logger.info(f"Receiving upload: {original_name} -> {safe_name}")

    # Stream file to disk
    try:
        async with aiofiles.open(save_path, "wb") as out_file:
            while chunk := await file.read(1024 * 1024):  # 1 MB chunks
                await out_file.write(chunk)
    except OSError as exc:
        logger.error(f"Failed to save upload to {save_path}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file.",
        )

    # Validate the saved file
    try:
        metadata = validate_video_file(save_path, original_name)
    except ValidationError as exc:
        # Clean up the invalid file
        save_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        )

    # Ensure a default project exists for the user
    projects = await crud.list_projects(db, user_id=user.id, limit=1)
    if projects:
        project_id = projects[0].id
    else:
        project = await crud.create_project(db, user_id=user.id, name="Default Project")
        project_id = project.id

    # Create the video record
    video = await crud.create_video(
        db,
        project_id=project_id,
        filename=original_name,
        filepath=str(save_path),
        **metadata,
    )

    logger.info(
        f"Video uploaded: id={video.id}, file={original_name}, size={metadata.get('filesize')}",
        extra={"video_id": video.id},
    )

    return VideoUploadResponse.model_validate(video)


@router.get(
    "/api/videos",
    response_model=VideoListResponse,
    summary="List uploaded videos",
    description="Return a paginated list of uploaded videos, most recent first.",
)
async def list_videos(
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    project_id: int | None = Query(None, description="Filter by project ID"),
    db: AsyncSession = Depends(get_db),
) -> VideoListResponse:
    """Return paginated video listing."""
    # Count total
    count_query = select(func.count(Video.id))
    if project_id is not None:
        count_query = count_query.where(Video.project_id == project_id)
    total = await db.scalar(count_query) or 0

    videos = await crud.list_videos(db, project_id=project_id, offset=offset, limit=limit)
    items = [VideoListItem.model_validate(v) for v in videos]

    return VideoListResponse(videos=items, total=total, offset=offset, limit=limit)


@router.get(
    "/api/videos/{video_id}",
    response_model=VideoDetail,
    responses={404: {"model": ErrorResponse}},
    summary="Get video detail",
    description="Return full video detail including clips, transcripts, and scenes.",
)
async def get_video_detail(
    video_id: int,
    db: AsyncSession = Depends(get_db),
) -> VideoDetail:
    """Retrieve a video with all related data."""
    video = await crud.get_video_with_relations(db, video_id)
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video with id {video_id} not found.",
        )
    return VideoDetail.model_validate(video)
