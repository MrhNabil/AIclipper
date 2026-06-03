"""
AIClipper CRUD Operations

Database create, read, update, delete operations for all models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database.models import (
    Clip,
    ClipStatus,
    Platform,
    Project,
    ProjectStatus,
    Scene,
    Setting,
    Subtitle,
    SubtitleFormat,
    Thumbnail,
    Transcript,
    Upload,
    UploadStatus,
    User,
    Video,
    VideoStatus,
)


# ===========================================================================
# User CRUD
# ===========================================================================

async def create_user(session: AsyncSession, username: str, email: str | None = None) -> User:
    user = User(username=username, email=email)
    session.add(user)
    await session.flush()
    return user


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_or_create_default_user(session: AsyncSession) -> User:
    """Get the default user, creating if needed (single-user mode)."""
    user = await get_user_by_username(session, "admin")
    if user is None:
        user = await create_user(session, "admin", "admin@localhost")
    return user


# ===========================================================================
# Project CRUD
# ===========================================================================

async def create_project(
    session: AsyncSession, user_id: int, name: str, description: str | None = None
) -> Project:
    project = Project(user_id=user_id, name=name, description=description)
    session.add(project)
    await session.flush()
    return project


async def get_project(session: AsyncSession, project_id: int) -> Project | None:
    return await session.get(Project, project_id)


async def list_projects(
    session: AsyncSession,
    user_id: int | None = None,
    status: ProjectStatus | None = None,
    offset: int = 0,
    limit: int = 50,
) -> Sequence[Project]:
    query = select(Project).order_by(Project.created_at.desc())
    if user_id is not None:
        query = query.where(Project.user_id == user_id)
    if status is not None:
        query = query.where(Project.status == status)
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


async def update_project(
    session: AsyncSession, project_id: int, **kwargs: Any
) -> Project | None:
    project = await get_project(session, project_id)
    if project:
        for key, value in kwargs.items():
            setattr(project, key, value)
        await session.flush()
    return project


# ===========================================================================
# Video CRUD
# ===========================================================================

async def create_video(
    session: AsyncSession,
    project_id: int,
    filename: str,
    filepath: str,
    **metadata: Any,
) -> Video:
    video = Video(
        project_id=project_id,
        filename=filename,
        filepath=filepath,
        **metadata,
    )
    session.add(video)
    await session.flush()
    return video


async def get_video(session: AsyncSession, video_id: int) -> Video | None:
    return await session.get(Video, video_id)


async def get_video_with_relations(session: AsyncSession, video_id: int) -> Video | None:
    result = await session.execute(
        select(Video)
        .options(
            selectinload(Video.clips).selectinload(Clip.subtitles),
            selectinload(Video.clips).selectinload(Clip.thumbnails),
            selectinload(Video.clips).selectinload(Clip.uploads),
            selectinload(Video.transcripts),
            selectinload(Video.scenes),
        )
        .where(Video.id == video_id)
    )
    return result.scalar_one_or_none()


async def list_videos(
    session: AsyncSession,
    project_id: int | None = None,
    status: VideoStatus | None = None,
    offset: int = 0,
    limit: int = 50,
) -> Sequence[Video]:
    query = select(Video).order_by(Video.created_at.desc())
    if project_id is not None:
        query = query.where(Video.project_id == project_id)
    if status is not None:
        query = query.where(Video.status == status)
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


async def update_video_status(
    session: AsyncSession,
    video_id: int,
    status: VideoStatus,
    progress: int | None = None,
    step: str | None = None,
    error: str | None = None,
) -> None:
    values: dict[str, Any] = {"status": status}
    if progress is not None:
        values["processing_progress"] = progress
    if step is not None:
        values["processing_step"] = step
    if error is not None:
        values["error_message"] = error
    await session.execute(update(Video).where(Video.id == video_id).values(**values))


# ===========================================================================
# Transcript CRUD
# ===========================================================================

async def create_transcript(
    session: AsyncSession,
    video_id: int,
    language: str,
    content_json: dict | list | None = None,
    word_timestamps_json: dict | list | None = None,
    full_text: str | None = None,
) -> Transcript:
    transcript = Transcript(
        video_id=video_id,
        language=language,
        content_json=content_json,
        word_timestamps_json=word_timestamps_json,
        full_text=full_text,
    )
    session.add(transcript)
    await session.flush()
    return transcript


async def get_transcript_for_video(session: AsyncSession, video_id: int) -> Transcript | None:
    result = await session.execute(
        select(Transcript).where(Transcript.video_id == video_id).order_by(Transcript.id.desc())
    )
    return result.scalar_one_or_none()


# ===========================================================================
# Scene CRUD
# ===========================================================================

async def create_scenes_batch(
    session: AsyncSession,
    video_id: int,
    scenes_data: list[dict[str, Any]],
) -> list[Scene]:
    scenes = []
    for i, data in enumerate(scenes_data):
        scene = Scene(
            video_id=video_id,
            scene_number=i + 1,
            start_time=data["start"],
            end_time=data["end"],
            duration=data["end"] - data["start"],
            score=data.get("score"),
            metadata_json=data.get("metadata"),
        )
        session.add(scene)
        scenes.append(scene)
    await session.flush()
    return scenes


async def get_scenes_for_video(session: AsyncSession, video_id: int) -> Sequence[Scene]:
    result = await session.execute(
        select(Scene).where(Scene.video_id == video_id).order_by(Scene.start_time)
    )
    return result.scalars().all()


# ===========================================================================
# Clip CRUD
# ===========================================================================

async def create_clip(
    session: AsyncSession,
    video_id: int,
    clip_number: int,
    start_time: float,
    end_time: float,
    total_score: float | None = None,
    score_breakdown: dict | None = None,
) -> Clip:
    clip = Clip(
        video_id=video_id,
        clip_number=clip_number,
        start_time=start_time,
        end_time=end_time,
        duration=end_time - start_time,
        total_score=total_score,
        score_breakdown_json=score_breakdown,
    )
    session.add(clip)
    await session.flush()
    return clip


async def get_clip(session: AsyncSession, clip_id: int) -> Clip | None:
    return await session.get(Clip, clip_id)


async def get_clip_with_relations(session: AsyncSession, clip_id: int) -> Clip | None:
    result = await session.execute(
        select(Clip)
        .options(
            selectinload(Clip.subtitles),
            selectinload(Clip.thumbnails),
            selectinload(Clip.uploads),
        )
        .where(Clip.id == clip_id)
    )
    return result.scalar_one_or_none()


async def list_clips(
    session: AsyncSession,
    video_id: int | None = None,
    status: ClipStatus | None = None,
    offset: int = 0,
    limit: int = 50,
) -> Sequence[Clip]:
    query = select(Clip).order_by(Clip.total_score.desc().nullslast())
    if video_id is not None:
        query = query.where(Clip.video_id == video_id)
    if status is not None:
        query = query.where(Clip.status == status)
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


async def update_clip(session: AsyncSession, clip_id: int, **kwargs: Any) -> Clip | None:
    clip = await get_clip(session, clip_id)
    if clip:
        for key, value in kwargs.items():
            setattr(clip, key, value)
        await session.flush()
    return clip


async def delete_clip(session: AsyncSession, clip_id: int) -> bool:
    result = await session.execute(delete(Clip).where(Clip.id == clip_id))
    return result.rowcount > 0


# ===========================================================================
# Subtitle CRUD
# ===========================================================================

async def create_subtitle(
    session: AsyncSession,
    clip_id: int,
    format: SubtitleFormat,
    filepath: str,
) -> Subtitle:
    subtitle = Subtitle(clip_id=clip_id, format=format, filepath=filepath)
    session.add(subtitle)
    await session.flush()
    return subtitle


async def get_subtitles_for_clip(session: AsyncSession, clip_id: int) -> Sequence[Subtitle]:
    result = await session.execute(
        select(Subtitle).where(Subtitle.clip_id == clip_id)
    )
    return result.scalars().all()


# ===========================================================================
# Thumbnail CRUD
# ===========================================================================

async def create_thumbnail(
    session: AsyncSession,
    clip_id: int,
    filepath: str,
    score: float | None = None,
    format: str = "jpg",
    width: int | None = None,
    height: int | None = None,
    is_selected: bool = False,
) -> Thumbnail:
    thumb = Thumbnail(
        clip_id=clip_id,
        filepath=filepath,
        score=score,
        format=format,
        width=width,
        height=height,
        is_selected=1 if is_selected else 0,
    )
    session.add(thumb)
    await session.flush()
    return thumb


async def get_selected_thumbnail(session: AsyncSession, clip_id: int) -> Thumbnail | None:
    result = await session.execute(
        select(Thumbnail)
        .where(Thumbnail.clip_id == clip_id, Thumbnail.is_selected == 1)
    )
    return result.scalar_one_or_none()


# ===========================================================================
# Upload CRUD
# ===========================================================================

async def create_upload(
    session: AsyncSession,
    clip_id: int,
    platform: Platform,
    scheduled_at: datetime | None = None,
) -> Upload:
    upload = Upload(
        clip_id=clip_id,
        platform=platform,
        scheduled_at=scheduled_at,
    )
    session.add(upload)
    await session.flush()
    return upload


async def update_upload(session: AsyncSession, upload_id: int, **kwargs: Any) -> Upload | None:
    upload = await session.get(Upload, upload_id)
    if upload:
        for key, value in kwargs.items():
            setattr(upload, key, value)
        await session.flush()
    return upload


async def list_uploads(
    session: AsyncSession,
    clip_id: int | None = None,
    platform: Platform | None = None,
    status: UploadStatus | None = None,
    offset: int = 0,
    limit: int = 50,
) -> Sequence[Upload]:
    query = select(Upload).order_by(Upload.created_at.desc())
    if clip_id is not None:
        query = query.where(Upload.clip_id == clip_id)
    if platform is not None:
        query = query.where(Upload.platform == platform)
    if status is not None:
        query = query.where(Upload.status == status)
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


# ===========================================================================
# Settings CRUD
# ===========================================================================

async def get_setting(session: AsyncSession, user_id: int, key: str) -> Any:
    result = await session.execute(
        select(Setting).where(Setting.user_id == user_id, Setting.key == key)
    )
    setting = result.scalar_one_or_none()
    return setting.value_json if setting else None


async def set_setting(session: AsyncSession, user_id: int, key: str, value: Any) -> Setting:
    result = await session.execute(
        select(Setting).where(Setting.user_id == user_id, Setting.key == key)
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value_json = value
    else:
        setting = Setting(user_id=user_id, key=key, value_json=value)
        session.add(setting)
    await session.flush()
    return setting


async def get_all_settings(session: AsyncSession, user_id: int) -> dict[str, Any]:
    result = await session.execute(
        select(Setting).where(Setting.user_id == user_id)
    )
    settings = result.scalars().all()
    return {s.key: s.value_json for s in settings}


# ===========================================================================
# Dashboard Stats
# ===========================================================================

async def get_dashboard_stats(session: AsyncSession) -> dict[str, Any]:
    """Get aggregate statistics for the dashboard."""
    video_count = await session.scalar(select(func.count(Video.id)))
    clip_count = await session.scalar(select(func.count(Clip.id)))
    completed_clips = await session.scalar(
        select(func.count(Clip.id)).where(Clip.status == ClipStatus.COMPLETED)
    )
    upload_count = await session.scalar(
        select(func.count(Upload.id)).where(Upload.status == UploadStatus.PUBLISHED)
    )
    project_count = await session.scalar(select(func.count(Project.id)))

    return {
        "total_videos": video_count or 0,
        "total_clips": clip_count or 0,
        "completed_clips": completed_clips or 0,
        "published_uploads": upload_count or 0,
        "total_projects": project_count or 0,
    }
