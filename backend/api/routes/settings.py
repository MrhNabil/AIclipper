"""
AIClipper Settings & Project Routes

Endpoints for managing user settings and projects.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.api.schemas import (
    ErrorResponse,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    SettingsResponse,
    SettingsUpdateRequest,
)
from backend.database import crud
from backend.database.models import Project, User
from backend.utils.logging import get_logger

logger = get_logger("api.settings")

router = APIRouter(tags=["Settings & Projects"])


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@router.get(
    "/api/settings",
    response_model=SettingsResponse,
    summary="Get user settings",
    description="Return all settings for the current user as key-value pairs.",
)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SettingsResponse:
    """Retrieve all settings for the authenticated user."""
    settings_dict = await crud.get_all_settings(db, user.id)
    return SettingsResponse(settings=settings_dict)


@router.put(
    "/api/settings",
    response_model=SettingsResponse,
    summary="Update user settings",
    description="Create or update one or more settings for the current user.",
)
async def update_settings(
    body: SettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SettingsResponse:
    """Update or create settings from the provided key-value pairs."""
    for key, value in body.settings.items():
        await crud.set_setting(db, user.id, key, value)

    logger.info(
        f"Settings updated for user {user.id}: {list(body.settings.keys())}",
    )

    # Return the complete settings after update
    settings_dict = await crud.get_all_settings(db, user.id)
    return SettingsResponse(settings=settings_dict)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@router.get(
    "/api/projects",
    response_model=ProjectListResponse,
    summary="List projects",
    description="Return a paginated list of projects for the current user.",
)
async def list_projects(
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectListResponse:
    """List projects belonging to the current user."""
    total_query = select(func.count(Project.id)).where(Project.user_id == user.id)
    total = await db.scalar(total_query) or 0

    projects = await crud.list_projects(db, user_id=user.id, offset=offset, limit=limit)
    items = [ProjectResponse.model_validate(p) for p in projects]

    return ProjectListResponse(projects=items, total=total, offset=offset, limit=limit)


@router.post(
    "/api/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}},
    summary="Create a project",
    description="Create a new project for the current user.",
)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectResponse:
    """Create a new project."""
    project = await crud.create_project(
        db,
        user_id=user.id,
        name=body.name,
        description=body.description,
    )

    logger.info(f"Project created: id={project.id}, name={body.name}")

    return ProjectResponse.model_validate(project)
