"""
AIClipper Database Models

SQLAlchemy ORM models for all application tables.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class VideoStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ClipStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadStatus(str, enum.Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    PUBLISHED = "published"
    SCHEDULED = "scheduled"
    FAILED = "failed"


class SubtitleFormat(str, enum.Enum):
    SRT = "srt"
    VTT = "vtt"
    BURNED = "burned"


class Platform(str, enum.Enum):
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("Setting", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="projects")
    videos = relationship("Video", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}')>"


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    filepath = Column(String(1000), nullable=False)
    duration = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    codec = Column(String(50), nullable=True)
    audio_codec = Column(String(50), nullable=True)
    bitrate = Column(Integer, nullable=True)
    filesize = Column(Integer, nullable=True)
    format_name = Column(String(50), nullable=True)
    status = Column(Enum(VideoStatus), default=VideoStatus.PENDING, nullable=False, index=True)
    processing_progress = Column(Integer, default=0)  # 0-100 percentage
    processing_step = Column(String(100), nullable=True)  # Current step name
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    project = relationship("Project", back_populates="videos")
    transcripts = relationship("Transcript", back_populates="video", cascade="all, delete-orphan")
    scenes = relationship("Scene", back_populates="video", cascade="all, delete-orphan")
    clips = relationship("Clip", back_populates="video", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Video(id={self.id}, filename='{self.filename}', status={self.status})>"


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    language = Column(String(10), nullable=False, default="en")
    content_json = Column(JSON, nullable=True)          # Full transcript segments
    word_timestamps_json = Column(JSON, nullable=True)  # Word-level timestamps
    full_text = Column(Text, nullable=True)              # Plain text transcript
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    video = relationship("Video", back_populates="transcripts")

    def __repr__(self) -> str:
        return f"<Transcript(id={self.id}, video_id={self.video_id}, lang='{self.language}')>"


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    scene_number = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    duration = Column(Float, nullable=False)
    score = Column(Float, nullable=True)
    metadata_json = Column(JSON, nullable=True)  # Additional scene metadata
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    video = relationship("Video", back_populates="scenes")

    def __repr__(self) -> str:
        return f"<Scene(id={self.id}, {self.start_time:.1f}s-{self.end_time:.1f}s)>"


class Clip(Base):
    __tablename__ = "clips"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    clip_number = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    duration = Column(Float, nullable=False)
    total_score = Column(Float, nullable=True)
    score_breakdown_json = Column(JSON, nullable=True)   # Per-factor scores
    output_path = Column(String(1000), nullable=True)
    status = Column(Enum(ClipStatus), default=ClipStatus.PENDING, nullable=False, index=True)
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    hashtags = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)
    crop_data_json = Column(JSON, nullable=True)         # Face tracking crop coordinates
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    video = relationship("Video", back_populates="clips")
    subtitles = relationship("Subtitle", back_populates="clip", cascade="all, delete-orphan")
    thumbnails = relationship("Thumbnail", back_populates="clip", cascade="all, delete-orphan")
    uploads = relationship("Upload", back_populates="clip", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Clip(id={self.id}, {self.start_time:.1f}s-{self.end_time:.1f}s, score={self.total_score})>"


class Subtitle(Base):
    __tablename__ = "subtitles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clip_id = Column(Integer, ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    format = Column(Enum(SubtitleFormat), nullable=False)
    filepath = Column(String(1000), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    clip = relationship("Clip", back_populates="subtitles")

    def __repr__(self) -> str:
        return f"<Subtitle(id={self.id}, format={self.format})>"


class Thumbnail(Base):
    __tablename__ = "thumbnails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clip_id = Column(Integer, ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    filepath = Column(String(1000), nullable=False)
    score = Column(Float, nullable=True)
    format = Column(String(10), nullable=False, default="jpg")  # png, jpg
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    is_selected = Column(Integer, default=0)  # Boolean (SQLite doesn't have bool)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    clip = relationship("Clip", back_populates="thumbnails")

    def __repr__(self) -> str:
        return f"<Thumbnail(id={self.id}, score={self.score}, selected={self.is_selected})>"


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clip_id = Column(Integer, ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(Enum(Platform), nullable=False)
    status = Column(Enum(UploadStatus), default=UploadStatus.PENDING, nullable=False, index=True)
    platform_video_id = Column(String(200), nullable=True)   # Platform-specific ID
    url = Column(String(1000), nullable=True)                  # Published URL
    scheduled_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, nullable=True)                # Platform-specific metadata
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    clip = relationship("Clip", back_populates="uploads")

    def __repr__(self) -> str:
        return f"<Upload(id={self.id}, platform={self.platform}, status={self.status})>"


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String(200), nullable=False)
    value_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="settings")

    # Unique constraint on (user_id, key)
    __table_args__ = (
        # SQLAlchemy unique constraint
        {"sqlite_autoincrement": True},
    )

    def __repr__(self) -> str:
        return f"<Setting(id={self.id}, key='{self.key}')>"
