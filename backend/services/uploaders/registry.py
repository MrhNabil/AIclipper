"""
AIClipper Uploader Registry

Registry pattern for platform uploaders. Allows registering new platforms
without modifying existing code.
"""

from __future__ import annotations

from typing import Type

from backend.services.uploaders.base import BaseUploader
from backend.utils.logging import get_logger

logger = get_logger("upload.registry")


class UploaderRegistry:
    """
    Registry of platform uploaders.

    Usage:
        registry = UploaderRegistry()
        registry.register("youtube", YouTubeUploader)
        uploader = registry.get("youtube")
    """

    _instance: UploaderRegistry | None = None
    _uploaders: dict[str, Type[BaseUploader]]

    def __init__(self) -> None:
        self._uploaders = {}

    @classmethod
    def get_instance(cls) -> UploaderRegistry:
        """Get the singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._register_defaults()
        return cls._instance

    def _register_defaults(self) -> None:
        """Register built-in uploaders."""
        try:
            from backend.services.uploaders.youtube import YouTubeUploader
            self.register("youtube", YouTubeUploader)
        except ImportError:
            logger.warning("YouTube uploader dependencies not available")

        try:
            from backend.services.uploaders.facebook import FacebookUploader
            self.register("facebook", FacebookUploader)
        except ImportError:
            logger.warning("Facebook uploader dependencies not available")

    def register(self, platform: str, uploader_cls: Type[BaseUploader]) -> None:
        """
        Register an uploader class for a platform.

        Args:
            platform: Platform identifier (lowercase)
            uploader_cls: Class implementing BaseUploader
        """
        platform = platform.lower()
        self._uploaders[platform] = uploader_cls
        logger.info(f"Registered uploader for platform: {platform}")

    def get(self, platform: str) -> BaseUploader:
        """
        Get an uploader instance for a platform.

        Args:
            platform: Platform identifier

        Returns:
            Instantiated BaseUploader subclass

        Raises:
            ValueError if platform not registered
        """
        platform = platform.lower()
        if platform not in self._uploaders:
            available = ", ".join(sorted(self._uploaders.keys()))
            raise ValueError(
                f"No uploader registered for platform '{platform}'. "
                f"Available: {available or 'none'}"
            )
        return self._uploaders[platform]()

    def list_platforms(self) -> list[str]:
        """Return list of registered platform names."""
        return sorted(self._uploaders.keys())

    def is_registered(self, platform: str) -> bool:
        """Check if a platform has a registered uploader."""
        return platform.lower() in self._uploaders
