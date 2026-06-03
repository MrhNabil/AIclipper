"""
AIClipper File Validators

Validates uploaded video files: format, size, codec, and integrity.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from backend.utils.config import get_settings
from backend.utils.logging import get_logger

logger = get_logger("validators")

# Supported video MIME type prefixes
SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov"}

# Magic bytes for common video formats
MAGIC_BYTES = {
    b"\x00\x00\x00": "mp4/mov",       # ftyp box (starts at offset 4, but first 3 often 0)
    b"\x1a\x45\xdf": "mkv/webm",      # EBML header
    b"RIFF": "avi",                     # AVI container
}


class ValidationError(Exception):
    """Raised when video validation fails."""

    def __init__(self, message: str, field: str = "file"):
        self.message = message
        self.field = field
        super().__init__(message)


def validate_file_extension(filename: str) -> str:
    """
    Validate that the file has a supported video extension.

    Returns the lowercase extension (e.g., '.mp4').
    Raises ValidationError if unsupported.
    """
    ext = Path(filename).suffix.lower()
    settings = get_settings()
    supported = {f".{fmt}" for fmt in settings.supported_formats}
    if ext not in supported:
        raise ValidationError(
            f"Unsupported file format '{ext}'. Supported: {', '.join(sorted(supported))}",
            field="format",
        )
    return ext


def validate_file_size(file_size: int) -> None:
    """
    Validate that the file doesn't exceed the maximum allowed size.

    Raises ValidationError if too large.
    """
    settings = get_settings()
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise ValidationError(
            f"File size ({file_size / (1024*1024):.1f} MB) exceeds maximum "
            f"allowed size ({settings.max_file_size_mb} MB)",
            field="size",
        )


def validate_magic_bytes(file_path: Path) -> bool:
    """
    Quick check that the file starts with recognized video magic bytes.

    Returns True if recognized, False if not (non-fatal check).
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(12)
        # Check for ftyp box (MP4/MOV) – 'ftyp' at offset 4
        if header[4:8] == b"ftyp":
            return True
        # Check EBML (MKV/WebM)
        if header[:4] == b"\x1a\x45\xdf\xa3":
            return True
        # Check RIFF (AVI)
        if header[:4] == b"RIFF":
            return True
        logger.warning(f"Unrecognized magic bytes for {file_path.name}")
        return False
    except (OSError, IndexError):
        return False


def probe_video(file_path: Path) -> dict[str, Any]:
    """
    Extract video metadata using FFprobe.

    Returns a dict with:
        - duration: float (seconds)
        - width: int
        - height: int
        - fps: float
        - codec: str
        - audio_codec: str
        - bitrate: int (bps)
        - filesize: int (bytes)
        - format_name: str

    Raises ValidationError if ffprobe fails or video is corrupt.
    """
    settings = get_settings()
    cmd = [
        settings.ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        data = json.loads(result.stdout)
    except FileNotFoundError:
        raise ValidationError(
            "FFprobe not found. Please install FFmpeg and ensure it's in your PATH.",
            field="system",
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"FFprobe failed for {file_path}: {e.stderr}")
        raise ValidationError(
            f"Could not read video file. It may be corrupt or unsupported. FFprobe error: {e.stderr[:200]}",
            field="file",
        )
    except subprocess.TimeoutExpired:
        raise ValidationError("FFprobe timed out analyzing the file.", field="file")
    except json.JSONDecodeError:
        raise ValidationError("FFprobe returned invalid data.", field="file")

    # Parse streams
    video_stream = None
    audio_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and video_stream is None:
            video_stream = stream
        elif stream.get("codec_type") == "audio" and audio_stream is None:
            audio_stream = stream

    if video_stream is None:
        raise ValidationError("No video stream found in the file.", field="file")

    # Parse FPS
    fps = 0.0
    r_frame_rate = video_stream.get("r_frame_rate", "0/1")
    if "/" in r_frame_rate:
        num, den = r_frame_rate.split("/")
        fps = float(num) / float(den) if float(den) > 0 else 0.0
    else:
        fps = float(r_frame_rate)

    # Parse duration
    duration = float(data.get("format", {}).get("duration", 0))
    if duration == 0:
        duration = float(video_stream.get("duration", 0))

    metadata = {
        "duration": duration,
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "fps": round(fps, 2),
        "codec": video_stream.get("codec_name", "unknown"),
        "audio_codec": audio_stream.get("codec_name", "none") if audio_stream else "none",
        "bitrate": int(data.get("format", {}).get("bit_rate", 0)),
        "filesize": int(data.get("format", {}).get("size", file_path.stat().st_size)),
        "format_name": data.get("format", {}).get("format_name", "unknown"),
    }

    return metadata


def validate_video_duration(duration: float) -> None:
    """
    Check that the video duration is within allowed limits.

    Raises ValidationError if too long.
    """
    settings = get_settings()
    if duration > settings.max_video_duration_seconds:
        hours = settings.max_video_duration_seconds / 3600
        raise ValidationError(
            f"Video duration ({duration/60:.1f} min) exceeds maximum "
            f"allowed duration ({hours:.0f} hours).",
            field="duration",
        )
    if duration < 5:
        raise ValidationError(
            "Video is too short (< 5 seconds). Please upload a longer video.",
            field="duration",
        )


def validate_video_file(file_path: Path, filename: str) -> dict[str, Any]:
    """
    Run all validation checks on a video file.

    Returns the video metadata dict if valid.
    Raises ValidationError on any failure.
    """
    # 1. Extension check
    validate_file_extension(filename)

    # 2. File existence
    if not file_path.exists():
        raise ValidationError("File not found.", field="file")

    # 3. File size
    validate_file_size(file_path.stat().st_size)

    # 4. Magic bytes (warning only)
    validate_magic_bytes(file_path)

    # 5. FFprobe metadata
    metadata = probe_video(file_path)

    # 6. Duration check
    validate_video_duration(metadata["duration"])

    logger.info(
        f"Video validated: {filename} | {metadata['duration']:.1f}s | "
        f"{metadata['width']}x{metadata['height']} | {metadata['codec']}",
        extra={"step": "validation"},
    )

    return metadata
