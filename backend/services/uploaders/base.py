"""
AIClipper Base Uploader

Abstract base class for all platform uploaders.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any


class UploadResult:
    """Result of a video upload operation."""

    def __init__(
        self,
        success: bool,
        platform_video_id: str | None = None,
        url: str | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.success = success
        self.platform_video_id = platform_video_id
        self.url = url
        self.error = error
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"<UploadResult(success={self.success}, id={self.platform_video_id})>"


class BaseUploader(ABC):
    """
    Abstract base class for platform uploaders.

    All platform-specific uploaders (YouTube, Facebook, TikTok, Instagram)
    must implement this interface. This ensures the upload module is fully
    modular — new platforms can be added without changing existing code.
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform identifier (e.g., 'youtube', 'facebook')."""
        ...

    @abstractmethod
    async def authenticate(self, credentials: dict[str, Any]) -> bool:
        """
        Authenticate with the platform.

        Args:
            credentials: Platform-specific credential data (tokens, secrets, etc.)

        Returns:
            True if authentication was successful
        """
        ...

    @abstractmethod
    async def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str] | None = None,
        privacy: str = "private",
        **kwargs: Any,
    ) -> UploadResult:
        """
        Upload a video to the platform.

        Args:
            video_path: Path to the video file
            title: Video title
            description: Video description
            tags: List of tags/hashtags
            privacy: Privacy setting (private, unlisted, public)

        Returns:
            UploadResult with platform video ID and URL
        """
        ...

    @abstractmethod
    async def upload_thumbnail(
        self,
        platform_video_id: str,
        thumbnail_path: Path,
    ) -> bool:
        """
        Upload a custom thumbnail for a video.

        Args:
            platform_video_id: The platform-specific video ID
            thumbnail_path: Path to the thumbnail image

        Returns:
            True if thumbnail upload was successful
        """
        ...

    @abstractmethod
    async def schedule_publish(
        self,
        platform_video_id: str,
        publish_at: datetime,
    ) -> bool:
        """
        Schedule a video for future publication.

        Args:
            platform_video_id: The platform-specific video ID
            publish_at: When to publish (UTC datetime)

        Returns:
            True if scheduling was successful
        """
        ...

    @abstractmethod
    async def get_status(self, platform_video_id: str) -> dict[str, Any]:
        """
        Get the current status of an uploaded video.

        Args:
            platform_video_id: The platform-specific video ID

        Returns:
            dict with status info (processing state, views, etc.)
        """
        ...
