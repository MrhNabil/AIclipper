"""
AIClipper Clip Routes

Endpoints for listing, viewing, deleting, and downloading generated clips.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db
from backend.api.schemas import (
    ClipDetailResponse,
    ClipListResponse,
    ClipResponse,
    ErrorResponse,
)
from backend.database import crud
from backend.database.models import Clip
from backend.utils.logging import get_logger

logger = get_logger("api.clips")

router = APIRouter(tags=["Clips"])


@router.get(
    "/api/clips",
    response_model=ClipListResponse,
    summary="List generated clips",
    description="Return a paginated list of clips, optionally filtered by video ID. "
    "Results are ordered by score descending.",
)
async def list_clips(
    video_id: int | None = Query(None, description="Filter clips by video ID"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    db: AsyncSession = Depends(get_db),
) -> ClipListResponse:
    """Return paginated clip listing."""
    count_query = select(func.count(Clip.id))
    if video_id is not None:
        count_query = count_query.where(Clip.video_id == video_id)
    total = await db.scalar(count_query) or 0

    clips = await crud.list_clips(db, video_id=video_id, offset=offset, limit=limit)
    items = [ClipResponse.model_validate(c) for c in clips]

    return ClipListResponse(clips=items, total=total, offset=offset, limit=limit)


@router.get(
    "/api/clips/{clip_id}",
    response_model=ClipDetailResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get clip detail",
    description="Return full clip detail with subtitles, thumbnails, and upload history.",
)
async def get_clip_detail(
    clip_id: int,
    db: AsyncSession = Depends(get_db),
) -> ClipDetailResponse:
    """Retrieve a clip with all related data."""
    clip = await crud.get_clip_with_relations(db, clip_id)
    if clip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clip with id {clip_id} not found.",
        )
    return ClipDetailResponse.model_validate(clip)


@router.delete(
    "/api/clips/{clip_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    summary="Delete a clip",
    description="Delete a clip record and remove its output file from disk.",
)
async def delete_clip(
    clip_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a clip and its associated file."""
    clip = await crud.get_clip(db, clip_id)
    if clip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clip with id {clip_id} not found.",
        )

    # Remove the output file if it exists
    if clip.output_path:
        output_file = Path(clip.output_path)
        if output_file.exists():
            try:
                output_file.unlink()
                logger.info(f"Deleted clip file: {output_file}", extra={"clip_id": clip_id})
            except OSError as exc:
                logger.warning(
                    f"Failed to delete clip file {output_file}: {exc}",
                    extra={"clip_id": clip_id},
                )

    deleted = await crud.delete_clip(db, clip_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clip with id {clip_id} could not be deleted.",
        )

    logger.info(f"Clip {clip_id} deleted", extra={"clip_id": clip_id})


@router.get(
    "/api/clips/{clip_id}/download",
    responses={
        404: {"model": ErrorResponse},
        200: {"content": {"video/mp4": {}}, "description": "Clip video file"},
    },
    summary="Download a clip",
    description="Serve the clip output file as a downloadable attachment.",
)
async def download_clip(
    clip_id: int,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Serve the clip file for download."""
    clip = await crud.get_clip(db, clip_id)
    if clip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clip with id {clip_id} not found.",
        )

    if not clip.output_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clip output file has not been generated yet.",
        )

    output_file = Path(clip.output_path)
    if not output_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clip output file not found on disk.",
        )

    download_name = f"clip_{clip.clip_number}_{clip.video_id}.mp4"

    return FileResponse(
        path=str(output_file),
        media_type="video/mp4",
        filename=download_name,
    )
