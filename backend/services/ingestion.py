"""
AIClipper Video Ingestion Service

Validates uploaded video files, extracts metadata via FFprobe, and creates
the initial Video database record so the processing pipeline can begin.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.database.engine import get_session_context
from backend.database import crud
from backend.utils.config import get_settings
from backend.utils.logging import get_logger, timed
from backend.utils.validators import validate_video_file, probe_video

logger = get_logger("services.ingestion")


@timed(logger_name="processing")
async def ingest_video(
    file_path: Path,
    filename: str,
    project_id: int,
) -> dict[str, Any]:
    """
    Validate a video file, extract metadata, and persist a Video record.

    Args:
        file_path: Absolute path to the uploaded video file on disk.
        filename: Original filename supplied by the user.
        project_id: ID of the project this video belongs to.

    Returns:
        A dict containing the new video's database id and its metadata::

            {
                "video_id": int,
                "filename": str,
                "filepath": str,
                "duration": float,
                "width": int,
                "height": int,
                "fps": float,
                "codec": str,
                "audio_codec": str,
                "bitrate": int,
                "filesize": int,
                "format_name": str,
            }

    Raises:
        backend.utils.validators.ValidationError: If the file fails any
            validation check (format, size, duration, corruption).
    """
    logger.info(f"Starting ingestion for '{filename}' (project_id={project_id})")

    # ── 1. Validate file ────────────────────────────────────────────────
    metadata = validate_video_file(file_path, filename)
    logger.info(
        f"Validation passed: {metadata['duration']:.1f}s, "
        f"{metadata['width']}x{metadata['height']}, {metadata['codec']}"
    )

    # ── 2. Create database record ───────────────────────────────────────
    async with get_session_context() as session:
        video = await crud.create_video(
            session,
            project_id=project_id,
            filename=filename,
            filepath=str(file_path),
            duration=metadata["duration"],
            width=metadata["width"],
            height=metadata["height"],
            fps=metadata["fps"],
            codec=metadata["codec"],
            audio_codec=metadata["audio_codec"],
            bitrate=metadata["bitrate"],
            filesize=metadata["filesize"],
            format_name=metadata["format_name"],
        )
        video_id: int = video.id  # captured before session closes

    logger.info(f"Video record created: id={video_id}")

    return {
        "video_id": video_id,
        "filename": filename,
        "filepath": str(file_path),
        **metadata,
    }
