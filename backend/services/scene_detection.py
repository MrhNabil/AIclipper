"""
AIClipper Scene Detection Service

Detects scene transitions in a video using PySceneDetect's ContentDetector
and returns structured scene boundary data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.utils.logging import get_logger, timed

logger = get_logger("services.scene_detection")


@timed(logger_name="processing")
def detect_scenes(
    video_path: Path,
    threshold: float = 27.0,
) -> list[dict[str, Any]]:
    """
    Detect scene changes in a video file.

    Uses *PySceneDetect* v0.7's ``detect()`` helper with a
    ``ContentDetector`` to find content-based scene transitions.

    Args:
        video_path: Path to the video file to analyse.
        threshold: Content-change threshold (lower → more sensitive).
            The default of 27.0 is recommended by PySceneDetect for most
            content.

    Returns:
        A list of scene dicts sorted by start time::

            [
                {
                    "start": float,          # seconds
                    "end": float,            # seconds
                    "duration": float,       # seconds
                    "score": float,          # 0-1 normalised transition density
                },
                ...
            ]

        Returns an empty list if PySceneDetect is not installed or the
        video cannot be read.
    """
    # ── 1. Import PySceneDetect ─────────────────────────────────────────
    try:
        from scenedetect import detect, ContentDetector  # type: ignore[import-untyped]
    except ImportError:
        logger.error(
            "PySceneDetect is not installed. "
            "Install with: pip install scenedetect[opencv]"
        )
        return []

    logger.info(
        f"Detecting scenes in '{video_path.name}' (threshold={threshold})"
    )

    try:
        raw_scenes = detect(str(video_path), ContentDetector(threshold=threshold))
    except Exception as exc:
        logger.error(f"Scene detection failed: {exc}", exc_info=True)
        return []

    if not raw_scenes:
        logger.info("No scene transitions detected.")
        return []

    # ── 2. Convert to structured dicts ──────────────────────────────────
    scenes: list[dict[str, Any]] = []
    for start_tc, end_tc in raw_scenes:
        start_s = start_tc.get_seconds()
        end_s = end_tc.get_seconds()
        duration = end_s - start_s
        scenes.append({
            "start": round(start_s, 3),
            "end": round(end_s, 3),
            "duration": round(duration, 3),
            "score": 0.0,  # will be normalised below
        })

    # ── 3. Compute normalised transition-density score ──────────────────
    # Score each scene by how short it is relative to the longest scene.
    # Shorter scenes (rapid cuts) receive a higher score.
    if scenes:
        max_duration = max(s["duration"] for s in scenes)
        if max_duration > 0:
            for scene in scenes:
                # Inverse-duration score: short scenes → higher score
                scene["score"] = round(
                    1.0 - (scene["duration"] / max_duration), 3
                )

    logger.info(f"Detected {len(scenes)} scenes in '{video_path.name}'")
    return scenes
