"""
AIClipper Publishing Routes

Endpoints for publishing clips to social platforms and fetching analytics.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
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
