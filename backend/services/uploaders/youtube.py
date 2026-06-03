"""
AIClipper YouTube Uploader

Upload videos and thumbnails to YouTube via the Data API v3.
Uses OAuth 2.0 for authentication with token persistence.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.services.uploaders.base import BaseUploader, UploadResult
from backend.utils.config import get_settings
from backend.utils.logging import get_logger

logger = get_logger("upload.youtube")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeUploader(BaseUploader):
    """YouTube Data API v3 uploader."""

    def __init__(self) -> None:
        self._credentials = None
        self._youtube = None

    @property
    def platform_name(self) -> str:
        return "youtube"

    async def authenticate(self, credentials: dict[str, Any]) -> bool:
        """
        Authenticate with YouTube via OAuth 2.0.

        credentials should contain:
          - client_secrets_file: path to client_secret.json (or use settings default)

        On first run, this will open a browser for OAuth consent.
        Subsequent runs use the cached token.
        """
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            logger.error("Google API libraries not installed. Run: pip install google-api-python-client google-auth-oauthlib")
            return False

        settings = get_settings()
        token_path = Path(credentials.get("token_file", str(settings.youtube_token_file)))
        secrets_path = Path(credentials.get("client_secrets_file", str(settings.youtube_client_secrets_file)))

        creds = None

        # Load cached token
        if token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            except Exception:
                logger.warning("Cached YouTube token is invalid, re-authenticating...")

        # Refresh or get new token
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if not secrets_path.exists():
                logger.error(f"Client secrets file not found: {secrets_path}")
                return False

            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
            creds = flow.run_local_server(port=8090, open_browser=True)

        # Save token for next time
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

        self._credentials = creds
        logger.info("YouTube authentication successful")
        return True

    def _get_service(self) -> Any:
        """Get the YouTube API service client."""
        if self._youtube is None:
            from googleapiclient.discovery import build
            self._youtube = build("youtube", "v3", credentials=self._credentials)
        return self._youtube

    async def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str] | None = None,
        privacy: str = "private",
        **kwargs: Any,
    ) -> UploadResult:
        """Upload a video to YouTube."""
        if not self._credentials:
            return UploadResult(success=False, error="Not authenticated. Call authenticate() first.")

        try:
            from googleapiclient.http import MediaFileUpload

            youtube = self._get_service()
            settings = get_settings()

            # Ensure #Shorts tag for vertical short-form content
            all_tags = list(tags or [])
            if "#Shorts" not in all_tags and "Shorts" not in all_tags:
                all_tags.append("Shorts")

            category_id = kwargs.get("category_id", "22")  # People & Blogs

            body = {
                "snippet": {
                    "title": title[:100],  # YouTube title limit
                    "description": description[:5000],
                    "tags": all_tags[:500],
                    "categoryId": category_id,
                },
                "status": {
                    "privacyStatus": privacy,
                    "selfDeclaredMadeForKids": False,
                },
            }

            # Handle scheduled publishing
            publish_at = kwargs.get("publish_at")
            if publish_at and isinstance(publish_at, datetime):
                body["status"]["publishAt"] = publish_at.isoformat() + "Z"
                body["status"]["privacyStatus"] = "private"

            media = MediaFileUpload(
                str(video_path),
                mimetype="video/mp4",
                resumable=True,
                chunksize=256 * 1024,  # 256KB chunks
            )

            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info(f"Upload progress: {int(status.progress() * 100)}%")

            video_id = response["id"]
            url = f"https://youtube.com/shorts/{video_id}"
            logger.info(f"YouTube upload successful: {url}")

            return UploadResult(
                success=True,
                platform_video_id=video_id,
                url=url,
                metadata=response,
            )

        except Exception as e:
            logger.error(f"YouTube upload failed: {e}")
            return UploadResult(success=False, error=str(e))

    async def upload_thumbnail(self, platform_video_id: str, thumbnail_path: Path) -> bool:
        """Upload a custom thumbnail for a YouTube video."""
        if not self._credentials:
            return False

        try:
            from googleapiclient.http import MediaFileUpload

            youtube = self._get_service()
            media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
            youtube.thumbnails().set(
                videoId=platform_video_id,
                media_body=media,
            ).execute()

            logger.info(f"Thumbnail uploaded for YouTube video {platform_video_id}")
            return True
        except Exception as e:
            logger.error(f"Thumbnail upload failed: {e}")
            return False

    async def schedule_publish(self, platform_video_id: str, publish_at: datetime) -> bool:
        """Schedule a YouTube video for future publication."""
        if not self._credentials:
            return False

        try:
            youtube = self._get_service()
            youtube.videos().update(
                part="status",
                body={
                    "id": platform_video_id,
                    "status": {
                        "privacyStatus": "private",
                        "publishAt": publish_at.isoformat() + "Z",
                    },
                },
            ).execute()

            logger.info(f"Scheduled YouTube video {platform_video_id} for {publish_at}")
            return True
        except Exception as e:
            logger.error(f"Schedule publish failed: {e}")
            return False

    async def get_status(self, platform_video_id: str) -> dict[str, Any]:
        """Get the status of a YouTube video."""
        if not self._credentials:
            return {"error": "Not authenticated"}

        try:
            youtube = self._get_service()
            response = youtube.videos().list(
                part="status,statistics",
                id=platform_video_id,
            ).execute()

            items = response.get("items", [])
            if not items:
                return {"error": "Video not found"}

            item = items[0]
            return {
                "upload_status": item.get("status", {}).get("uploadStatus"),
                "privacy_status": item.get("status", {}).get("privacyStatus"),
                "publish_at": item.get("status", {}).get("publishAt"),
                "views": int(item.get("statistics", {}).get("viewCount", 0)),
                "likes": int(item.get("statistics", {}).get("likeCount", 0)),
            }
        except Exception as e:
            logger.error(f"Get status failed: {e}")
            return {"error": str(e)}
