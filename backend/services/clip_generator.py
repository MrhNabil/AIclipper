"""
AIClipper Clip Generation Service

Cuts clips from the source video and optionally applies face-aware 9:16
cropping for vertical short-form output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.utils.config import get_settings
from backend.utils.ffmpeg import apply_dynamic_crop, convert_vertical, cut_clip
from backend.utils.logging import get_logger, timed

logger = get_logger("services.clip_generator")


def _crop_data_for_range(
    crop_data: list[dict[str, Any]],
    start_time: float,
    end_time: float,
) -> list[dict[str, Any]]:
    """
    Filter and re-base crop data to the clip time range.

    Args:
        crop_data: Full-video crop timeline from face tracking.
        start_time: Clip start in seconds.
        end_time: Clip end in seconds.

    Returns:
        Filtered crop data list with ``time`` values relative to clip start.
    """
    filtered: list[dict[str, Any]] = []
    for entry in crop_data:
        t = entry["time"]
        if start_time <= t <= end_time:
            rebased = dict(entry)
            rebased["time"] = round(t - start_time, 3)
            filtered.append(rebased)
    return filtered


@timed(logger_name="processing")
def generate_clip(
    video_path: Path,
    output_path: Path,
    start_time: float,
    end_time: float,
    crop_data: list[dict[str, Any]] | None = None,
) -> Path:
    """
    Generate a single clip from a source video.

    Steps:
        1. Cut the time range from the source video (stream-copy for speed).
        2. If *crop_data* is provided, apply face-aware dynamic cropping
           to produce a 1080×1920 vertical output.  Otherwise, convert to
           vertical with centre-pad.
        3. Return the path to the final clip file.

    Args:
        video_path: Source video path.
        output_path: Desired output file path (e.g. ``clip_001.mp4``).
        start_time: Clip start in seconds.
        end_time: Clip end in seconds.
        crop_data: Optional face-tracking crop timeline for the *entire*
            source video.  Will be filtered to the clip range internally.

    Returns:
        Path to the generated clip file.

    Raises:
        RuntimeError: If FFmpeg operations fail.
    """
    settings = get_settings()
    duration = end_time - start_time

    logger.info(
        f"Generating clip {start_time:.1f}s – {end_time:.1f}s "
        f"({duration:.1f}s) from '{video_path.name}'"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ── 1. Cut the raw segment ──────────────────────────────────────────
    raw_cut_path = output_path.with_name(output_path.stem + "_raw" + output_path.suffix)
    cut_clip(
        input_path=video_path,
        output_path=raw_cut_path,
        start_time=start_time,
        duration=duration,
        reencode=False,  # fast stream-copy
    )

    # ── 2. Apply crop / vertical conversion ─────────────────────────────
    try:
        if crop_data:
            clip_crops = _crop_data_for_range(crop_data, start_time, end_time)
            if clip_crops:
                apply_dynamic_crop(raw_cut_path, output_path, clip_crops)
            else:
                convert_vertical(raw_cut_path, output_path)
        else:
            convert_vertical(raw_cut_path, output_path)
    finally:
        # Clean up intermediate raw cut
        try:
            if raw_cut_path.exists():
                raw_cut_path.unlink()
        except OSError:
            pass

    logger.info(f"Clip generated: {output_path.name}")
    return output_path
