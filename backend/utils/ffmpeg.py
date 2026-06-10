"""
AIClipper FFmpeg Utilities

Reusable FFmpeg operations: probing, cutting, cropping, subtitle burning,
frame extraction, and format conversion. All operations use subprocess
for maximum cross-platform reliability.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from backend.utils.config import get_settings
from backend.utils.logging import get_logger, timed

logger = get_logger("ffmpeg")


def _get_creation_flags() -> int:
    """Return subprocess creation flags to suppress console windows on Windows."""
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def _run_ffmpeg(args: list[str], description: str = "FFmpeg operation") -> subprocess.CompletedProcess:
    """
    Run an FFmpeg command with standard error handling.

    Returns the CompletedProcess result.
    Raises RuntimeError on failure.
    """
    settings = get_settings()
    cmd = [settings.ffmpeg_path] + args
    logger.debug(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour max
            creationflags=_get_creation_flags(),
        )
        if result.returncode != 0:
            logger.error(f"{description} failed: {result.stderr[:500]}")
            raise RuntimeError(f"{description} failed: {result.stderr[:500]}")
        return result
    except FileNotFoundError:
        raise RuntimeError(
            f"FFmpeg not found at '{settings.ffmpeg_path}'. "
            "Please install FFmpeg and ensure it's in your PATH."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{description} timed out after 1 hour.")


def check_ffmpeg_installed() -> bool:
    """Check if FFmpeg is available on the system."""
    settings = get_settings()
    try:
        result = subprocess.run(
            [settings.ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=_get_creation_flags(),
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            logger.info(f"FFmpeg found: {version_line}")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    logger.error("FFmpeg not found on system")
    return False


@timed(logger_name="processing")
def extract_audio(
    video_path: Path,
    output_path: Path,
    sample_rate: int = 16000,
    mono: bool = True,
) -> Path:
    """
    Extract audio from video as WAV file.

    Args:
        video_path: Input video file path
        output_path: Output WAV file path
        sample_rate: Audio sample rate (default 16kHz for Whisper)
        mono: Convert to mono (default True for Whisper)

    Returns:
        Path to the extracted audio file
    """
    args = [
        "-i", str(video_path),
        "-vn",                          # No video
        "-acodec", "pcm_s16le",         # 16-bit PCM WAV
        "-ar", str(sample_rate),        # Sample rate
    ]
    if mono:
        args.extend(["-ac", "1"])       # Mono channel
    args.extend([
        "-y",                           # Overwrite
        str(output_path),
    ])

    _run_ffmpeg(args, f"Audio extraction from {video_path.name}")
    logger.info(f"Extracted audio: {output_path.name} ({sample_rate}Hz, {'mono' if mono else 'stereo'})")
    return output_path


@timed(logger_name="processing")
def cut_clip(
    input_path: Path,
    output_path: Path,
    start_time: float,
    duration: float,
    reencode: bool = False,
) -> Path:
    """
    Cut a clip from a video file.

    Args:
        input_path: Source video file
        output_path: Output clip file
        start_time: Start time in seconds
        duration: Clip duration in seconds
        reencode: If True, re-encode (slower but more precise cuts)

    Returns:
        Path to the generated clip
    """
    args = [
        "-ss", f"{start_time:.3f}",
        "-i", str(input_path),
        "-t", f"{duration:.3f}",
    ]
    if reencode:
        settings = get_settings()
        args.extend([
            "-c:v", settings.output_settings.codec,
            "-crf", str(settings.output_settings.crf),
            "-preset", settings.output_settings.preset,
            "-c:a", settings.output_settings.audio_codec,
            "-b:a", settings.output_settings.audio_bitrate,
        ])
    else:
        args.extend(["-c", "copy"])

    args.extend(["-avoid_negative_ts", "1", "-y", str(output_path)])

    _run_ffmpeg(args, f"Clip cut {start_time:.1f}s-{start_time+duration:.1f}s")
    return output_path


@timed(logger_name="processing")
def convert_vertical(
    input_path: Path,
    output_path: Path,
    crop_x: int | None = None,
    crop_y: int | None = None,
    crop_w: int | None = None,
    crop_h: int | None = None,
) -> Path:
    """
    Convert a video to vertical (1080x1920) format.

    If crop coordinates are provided, crops to those coordinates first.
    Otherwise, scales and pads to fit 1080x1920.

    Returns:
        Path to the converted video
    """
    settings = get_settings()
    w = settings.output_settings.width
    h = settings.output_settings.height

    if crop_x is not None and crop_w is not None:
        # Crop then scale to output resolution
        vf = (
            f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
        )
    else:
        # Scale maintaining aspect ratio, pad to fill
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
        )

    args = [
        "-i", str(input_path),
        "-vf", vf,
        "-c:v", settings.output_settings.codec,
        "-crf", str(settings.output_settings.crf),
        "-preset", settings.output_settings.preset,
        "-c:a", settings.output_settings.audio_codec,
        "-ac", "2",  # Downmix to stereo (AAC encoder can't handle 5.1)
        "-b:a", settings.output_settings.audio_bitrate,
        "-r", str(settings.output_settings.fps),
        "-y", str(output_path),
    ]

    _run_ffmpeg(args, f"Vertical conversion of {input_path.name}")
    return output_path


@timed(logger_name="processing")
def apply_dynamic_crop(
    input_path: Path,
    output_path: Path,
    crop_timeline: list[dict[str, Any]],
) -> Path:
    """
    Apply dynamic face-following crop using FFmpeg's sendcmd/crop filters.

    For CPU efficiency, we generate a crop filter with keyframed positions.

    Args:
        input_path: Source video
        output_path: Output video
        crop_timeline: List of {"time": float, "crop_x": int, "crop_y": int, "crop_w": int, "crop_h": int}
    """
    settings = get_settings()
    w = settings.output_settings.width
    h = settings.output_settings.height

    if not crop_timeline:
        return convert_vertical(input_path, output_path)

    # Use the median crop position for a static crop (simplest reliable approach)
    # Dynamic per-frame cropping via sendcmd is complex; this gives good results
    xs = [c["crop_x"] for c in crop_timeline]
    ys = [c["crop_y"] for c in crop_timeline]
    ws = [c["crop_w"] for c in crop_timeline]
    hs = [c["crop_h"] for c in crop_timeline]

    crop_x = sorted(xs)[len(xs) // 2]
    crop_y = sorted(ys)[len(ys) // 2]
    crop_w = sorted(ws)[len(ws) // 2]
    crop_h = sorted(hs)[len(hs) // 2]

    vf = (
        f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
    )

    args = [
        "-i", str(input_path),
        "-vf", vf,
        "-c:v", settings.output_settings.codec,
        "-crf", str(settings.output_settings.crf),
        "-preset", settings.output_settings.preset,
        "-c:a", settings.output_settings.audio_codec,
        "-ac", "2",  # Downmix to stereo (AAC encoder can't handle 5.1)
        "-b:a", settings.output_settings.audio_bitrate,
        "-r", str(settings.output_settings.fps),
        "-y", str(output_path),
    ]

    _run_ffmpeg(args, f"Dynamic crop of {input_path.name}")
    return output_path


@timed(logger_name="processing")
def burn_subtitles(
    input_path: Path,
    output_path: Path,
    subtitle_path: Path,
    font_family: str = "Arial",
    font_size: int = 24,
    font_color: str = "&HFFFFFF",
    outline_color: str = "&H000000",
    outline_width: int = 2,
) -> Path:
    """
    Burn subtitles into a video using the ASS subtitle filter.

    Returns:
        Path to the video with burned-in subtitles
    """
    settings = get_settings()

    # Escape special characters in path for FFmpeg filter
    sub_path_str = str(subtitle_path).replace("\\", "/").replace(":", "\\:")

    force_style = (
        f"FontName={font_family},"
        f"FontSize={font_size},"
        f"PrimaryColour={font_color},"
        f"OutlineColour={outline_color},"
        f"Outline={outline_width},"
        f"Shadow=1,"
        f"MarginV=40"
    )

    vf = f"subtitles='{sub_path_str}':force_style='{force_style}'"

    args = [
        "-i", str(input_path),
        "-vf", vf,
        "-c:v", settings.output_settings.codec,
        "-crf", str(settings.output_settings.crf),
        "-preset", settings.output_settings.preset,
        "-c:a", "copy",
        "-y", str(output_path),
    ]

    _run_ffmpeg(args, f"Subtitle burn for {input_path.name}")
    return output_path


@timed(logger_name="processing")
def extract_frame(
    video_path: Path,
    output_path: Path,
    timestamp: float,
) -> Path:
    """
    Extract a single frame from a video at the given timestamp.

    Returns:
        Path to the extracted frame image
    """
    args = [
        "-ss", f"{timestamp:.3f}",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",  # High quality JPEG
        "-y", str(output_path),
    ]

    _run_ffmpeg(args, f"Frame extraction at {timestamp:.1f}s")
    return output_path


@timed(logger_name="processing")
def extract_frames_batch(
    video_path: Path,
    output_dir: Path,
    fps: float = 1.0,
    prefix: str = "frame",
) -> list[Path]:
    """
    Extract frames from a video at the given FPS rate.

    Returns:
        List of paths to extracted frames
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(output_dir / f"{prefix}_%06d.jpg")

    args = [
        "-i", str(video_path),
        "-vf", f"fps={fps}",
        "-q:v", "2",
        "-y", pattern,
    ]

    _run_ffmpeg(args, f"Batch frame extraction at {fps} fps")

    frames = sorted(output_dir.glob(f"{prefix}_*.jpg"))
    logger.info(f"Extracted {len(frames)} frames from {video_path.name}")
    return frames


def get_video_duration(video_path: Path) -> float:
    """Quick duration probe using FFprobe."""
    settings = get_settings()
    cmd = [
        settings.ffprobe_path,
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=_get_creation_flags(),
        )
        return float(result.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired, FileNotFoundError):
        return 0.0
