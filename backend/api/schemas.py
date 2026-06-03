"""
AIClipper API Schemas

Pydantic v2 request/response schemas for all API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Common / Error
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Standard error response returned by all endpoints on failure."""

    detail: str = Field(..., description="Human-readable error message")
    field: str | None = Field(None, description="Field that caused the error, if applicable")

    model_config = {"json_schema_extra": {"examples": [{"detail": "Video not found", "field": None}]}}


# ---------------------------------------------------------------------------
# Video Schemas
# ---------------------------------------------------------------------------

class VideoUploadResponse(BaseModel):
    """Response returned after a successful video upload."""

    id: int = Field(..., description="Unique video ID")
    filename: str = Field(..., description="Original filename")
    filepath: str = Field(..., description="Server-side file path")
    status: str = Field(..., description="Current processing status")
    duration: float | None = Field(None, description="Video duration in seconds")
    width: int | None = Field(None, description="Video width in pixels")
    height: int | None = Field(None, description="Video height in pixels")
    fps: float | None = Field(None, description="Frames per second")
    codec: str | None = Field(None, description="Video codec")
    filesize: int | None = Field(None, description="File size in bytes")
    created_at: datetime = Field(..., description="Upload timestamp")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "filename": "interview.mp4",
                    "filepath": "uploads/interview.mp4",
                    "status": "pending",
                    "duration": 1234.5,
                    "width": 1920,
                    "height": 1080,
                    "fps": 30.0,
                    "codec": "h264",
                    "filesize": 104857600,
                    "created_at": "2026-01-15T10:30:00",
                }
            ]
        },
    }


class TranscriptSchema(BaseModel):
    """Transcript data associated with a video."""

    id: int
    language: str = Field(..., description="Language code, e.g. 'en'")
    full_text: str | None = Field(None, description="Plain text transcript")
    content_json: Any | None = Field(None, description="Structured transcript segments")
    created_at: datetime

    model_config = {"from_attributes": True}


class SceneSchema(BaseModel):
    """Scene boundary detected in a video."""

    id: int
    scene_number: int
    start_time: float = Field(..., description="Scene start in seconds")
    end_time: float = Field(..., description="Scene end in seconds")
    duration: float
    score: float | None = None

    model_config = {"from_attributes": True}


class SubtitleSchema(BaseModel):
    """Subtitle file linked to a clip."""

    id: int
    format: str
    filepath: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ThumbnailSchema(BaseModel):
    """Thumbnail image for a clip."""

    id: int
    filepath: str
    score: float | None = None
    format: str
    width: int | None = None
    height: int | None = None
    is_selected: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadSchema(BaseModel):
    """Platform upload record."""

    id: int
    platform: str
    status: str
    platform_video_id: str | None = None
    url: str | None = None
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClipSummary(BaseModel):
    """Compact clip representation used in video detail views."""

    id: int
    clip_number: int
    start_time: float
    end_time: float
    duration: float
    total_score: float | None = None
    title: str | None = None
    status: str
    output_path: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoDetail(BaseModel):
    """Detailed video representation including related clips and transcripts."""

    id: int
    project_id: int
    filename: str
    filepath: str
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    codec: str | None = None
    audio_codec: str | None = None
    bitrate: int | None = None
    filesize: int | None = None
    format_name: str | None = None
    status: str
    processing_progress: int = 0
    processing_step: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    clips: list[ClipSummary] = Field(default_factory=list)
    transcripts: list[TranscriptSchema] = Field(default_factory=list)
    scenes: list[SceneSchema] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class VideoListItem(BaseModel):
    """Compact video representation for list views."""

    id: int
    project_id: int
    filename: str
    duration: float | None = None
    status: str
    processing_progress: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoListResponse(BaseModel):
    """Paginated list of videos."""

    videos: list[VideoListItem]
    total: int = Field(..., description="Total number of videos matching the query")
    offset: int = Field(0, description="Current offset")
    limit: int = Field(50, description="Page size")


# ---------------------------------------------------------------------------
# Processing Schemas
# ---------------------------------------------------------------------------

class ProcessingStatusResponse(BaseModel):
    """Current processing status for a video."""

    video_id: int = Field(..., description="Video ID being processed")
    status: str = Field(..., description="Processing status: pending, processing, completed, failed")
    progress: int = Field(0, description="Processing progress 0-100", ge=0, le=100)
    step: str | None = Field(None, description="Current processing step name")
    error_message: str | None = Field(None, description="Error message if status is 'failed'")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "video_id": 1,
                    "status": "processing",
                    "progress": 45,
                    "step": "transcription",
                    "error_message": None,
                }
            ]
        }
    }


# ---------------------------------------------------------------------------
# Clip Schemas
# ---------------------------------------------------------------------------

class ClipResponse(BaseModel):
    """Clip in a list view."""

    id: int
    video_id: int
    clip_number: int
    start_time: float
    end_time: float
    duration: float
    total_score: float | None = None
    title: str | None = None
    description: str | None = None
    status: str
    output_path: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClipListResponse(BaseModel):
    """Paginated list of clips."""

    clips: list[ClipResponse]
    total: int = Field(..., description="Total number of clips matching the query")
    offset: int = 0
    limit: int = 50


class ClipDetailResponse(BaseModel):
    """Full clip detail with subtitles, thumbnails, and upload history."""

    id: int
    video_id: int
    clip_number: int
    start_time: float
    end_time: float
    duration: float
    total_score: float | None = None
    score_breakdown_json: dict[str, Any] | None = None
    title: str | None = None
    description: str | None = None
    hashtags: str | None = None
    keywords: str | None = None
    status: str
    output_path: str | None = None
    crop_data_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None
    subtitles: list[SubtitleSchema] = Field(default_factory=list)
    thumbnails: list[ThumbnailSchema] = Field(default_factory=list)
    uploads: list[UploadSchema] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Publishing Schemas
# ---------------------------------------------------------------------------

class PublishRequest(BaseModel):
    """Request to publish a clip to a platform."""

    clip_id: int = Field(..., description="ID of the clip to publish")
    platform: str = Field(
        ...,
        description="Target platform: youtube, facebook, tiktok, instagram",
    )
    scheduled_at: datetime | None = Field(
        None,
        description="Optional scheduled publish time (ISO 8601)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"clip_id": 1, "platform": "youtube", "scheduled_at": None}]
        }
    }


class PublishResponse(BaseModel):
    """Response after creating a publish job."""

    id: int = Field(..., description="Upload record ID")
    clip_id: int
    platform: str
    status: str
    scheduled_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Analytics Schemas
# ---------------------------------------------------------------------------

class AnalyticsResponse(BaseModel):
    """Dashboard aggregate statistics."""

    total_videos: int = Field(0, description="Total uploaded videos")
    total_clips: int = Field(0, description="Total generated clips")
    completed_clips: int = Field(0, description="Clips in completed status")
    published_uploads: int = Field(0, description="Successfully published uploads")
    total_projects: int = Field(0, description="Total projects")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "total_videos": 12,
                    "total_clips": 48,
                    "completed_clips": 42,
                    "published_uploads": 15,
                    "total_projects": 3,
                }
            ]
        }
    }


# ---------------------------------------------------------------------------
# Project Schemas
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    """Request to create a new project."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Project name",
    )
    description: str | None = Field(None, max_length=2000, description="Optional description")

    model_config = {
        "json_schema_extra": {"examples": [{"name": "My Podcast Clips", "description": "Weekly podcast highlights"}]}
    }


class ProjectResponse(BaseModel):
    """Single project."""

    id: int
    user_id: int
    name: str
    description: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Paginated list of projects."""

    projects: list[ProjectResponse]
    total: int = Field(..., description="Total number of projects")
    offset: int = 0
    limit: int = 50


# ---------------------------------------------------------------------------
# Settings Schemas
# ---------------------------------------------------------------------------

class SettingsResponse(BaseModel):
    """All user settings as key-value pairs."""

    settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value mapping of user settings",
    )


class SettingsUpdateRequest(BaseModel):
    """Request to update one or more settings."""

    settings: dict[str, Any] = Field(
        ...,
        description="Key-value pairs to create or update",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "settings": {
                        "theme": "dark",
                        "default_clip_duration": 30,
                        "auto_generate_subtitles": True,
                    }
                }
            ]
        }
    }
