"""
AIClipper Facebook Uploader

Upload Reels to Facebook Pages via the Graph API.
Uses the 3-step resumable upload protocol.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from backend.services.uploaders.base import BaseUploader, UploadResult
from backend.utils.config import get_settings
from backend.utils.logging import get_logger

logger = get_logger("upload.facebook")

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


class FacebookUploader(BaseUploader):
    """Facebook Graph API Reel uploader."""

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._page_id: str | None = None

    @property
    def platform_name(self) -> str:
        return "facebook"

    async def authenticate(self, credentials: dict[str, Any]) -> bool:
        """
        Authenticate with Facebook.

        credentials should contain:
          - access_token: Page Access Token with CREATE_CONTENT permission
          - page_id: Facebook Page ID

        The token should have permissions:
          - pages_show_list
          - pages_read_engagement
          - pages_manage_posts
        """
        self._access_token = credentials.get("access_token")
        self._page_id = credentials.get("page_id")

        if not self._access_token:
            settings = get_settings()
            self._access_token = settings.facebook_access_token
            self._page_id = settings.facebook_page_id

        if not self._access_token or not self._page_id:
            logger.error("Facebook access token and page ID are required")
            return False

        # Verify token validity
        try:
            resp = requests.get(
                f"{GRAPH_API_BASE}/me",
                params={"access_token": self._access_token},
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info(f"Facebook authentication successful for page {self._page_id}")
                return True
            else:
                logger.error(f"Facebook auth failed: {resp.json()}")
                return False
        except Exception as e:
            logger.error(f"Facebook auth request failed: {e}")
            return False

    async def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str] | None = None,
        privacy: str = "PUBLISHED",
        **kwargs: Any,
    ) -> UploadResult:
        """
        Upload a Reel to Facebook using the 3-step protocol.

        Step 1: Initialize upload session → get video_id + upload_url
        Step 2: Upload video binary to upload_url
        Step 3: Publish the reel
        """
        if not self._access_token or not self._page_id:
            return UploadResult(success=False, error="Not authenticated")

        try:
            # --- Step 1: Initialize upload ---
            logger.info("Facebook upload Step 1: Initializing...")
            init_resp = requests.post(
                f"{GRAPH_API_BASE}/{self._page_id}/video_reels",
                data={
                    "upload_phase": "start",
                    "access_token": self._access_token,
                },
                timeout=30,
            )

            if init_resp.status_code != 200:
                error_data = init_resp.json().get("error", {})
                return UploadResult(
                    success=False,
                    error=f"Init failed: {error_data.get('message', init_resp.text)}",
                )

            init_data = init_resp.json()
            video_id = init_data["video_id"]
            upload_url = init_data.get("upload_url")

            if not upload_url:
                return UploadResult(
                    success=False,
                    error="No upload URL received from Facebook",
                )

            # --- Step 2: Upload binary ---
            logger.info(f"Facebook upload Step 2: Uploading binary ({video_path.stat().st_size / (1024*1024):.1f} MB)...")
            file_size = video_path.stat().st_size

            with open(video_path, "rb") as f:
                upload_resp = requests.post(
                    upload_url,
                    data=f,
                    headers={
                        "Authorization": f"OAuth {self._access_token}",
                        "offset": "0",
                        "file_size": str(file_size),
                        "Content-Type": "application/octet-stream",
                    },
                    timeout=600,  # 10 min for large files
                )

            if upload_resp.status_code not in (200, 201):
                return UploadResult(
                    success=False,
                    error=f"Binary upload failed: {upload_resp.text}",
                )

            # --- Step 3: Publish ---
            logger.info("Facebook upload Step 3: Publishing...")

            # Build description with hashtags
            full_description = description
            if tags:
                hashtags = " ".join(t if t.startswith("#") else f"#{t}" for t in tags)
                full_description = f"{description}\n\n{hashtags}"

            video_state = kwargs.get("video_state", "PUBLISHED")
            publish_data: dict[str, Any] = {
                "upload_phase": "finish",
                "video_id": video_id,
                "title": title[:100],
                "description": full_description[:2000],
                "video_state": video_state,
                "access_token": self._access_token,
            }

            # Handle scheduled publishing
            publish_at = kwargs.get("publish_at")
            if publish_at and isinstance(publish_at, datetime):
                publish_data["video_state"] = "SCHEDULED"
                publish_data["scheduled_publish_time"] = int(publish_at.timestamp())

            finish_resp = requests.post(
                f"{GRAPH_API_BASE}/{self._page_id}/video_reels",
                data=publish_data,
                timeout=30,
            )

            if finish_resp.status_code != 200:
                error_data = finish_resp.json().get("error", {})
                return UploadResult(
                    success=False,
                    error=f"Publish failed: {error_data.get('message', finish_resp.text)}",
                )

            result_data = finish_resp.json()
            url = f"https://www.facebook.com/reel/{video_id}"
            logger.info(f"Facebook reel uploaded successfully: {url}")

            return UploadResult(
                success=True,
                platform_video_id=video_id,
                url=url,
                metadata=result_data,
            )

        except requests.Timeout:
            return UploadResult(success=False, error="Upload timed out")
        except Exception as e:
            logger.error(f"Facebook upload failed: {e}")
            return UploadResult(success=False, error=str(e))

    async def upload_thumbnail(self, platform_video_id: str, thumbnail_path: Path) -> bool:
        """Facebook Reels don't support custom thumbnail upload via API."""
        logger.info("Facebook Reels: Custom thumbnail upload is not supported via the API")
        return False

    async def schedule_publish(self, platform_video_id: str, publish_at: datetime) -> bool:
        """Schedule is handled during the upload step for Facebook."""
        logger.info("Facebook: Schedule is set during upload, not separately")
        return True

    async def get_status(self, platform_video_id: str) -> dict[str, Any]:
        """Get the status of a Facebook Reel."""
        if not self._access_token:
            return {"error": "Not authenticated"}

        try:
            resp = requests.get(
                f"{GRAPH_API_BASE}/{platform_video_id}",
                params={
                    "fields": "status,views,likes.summary(true)",
                    "access_token": self._access_token,
                },
                timeout=10,
            )

            if resp.status_code == 200:
                data = resp.json()
                return {
                    "status": data.get("status", {}).get("video_status"),
                    "views": data.get("views"),
                    "likes": data.get("likes", {}).get("summary", {}).get("total_count", 0),
                }
            else:
                return {"error": resp.json().get("error", {}).get("message", "Unknown error")}
        except Exception as e:
            return {"error": str(e)}
