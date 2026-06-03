"""
AIClipper Thumbnail Generation Service

Extracts candidate frames from the best moments in a clip, scores each for
visual quality (sharpness, brightness, face presence), and exports the top
candidates as PNG and JPG.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from backend.utils.config import get_settings
from backend.utils.ffmpeg import extract_frame
from backend.utils.logging import get_logger, timed

logger = get_logger("services.thumbnail_generator")


# ── Scoring helpers ─────────────────────────────────────────────────────

def _score_sharpness(image_array: np.ndarray) -> float:
    """
    Estimate image sharpness via Laplacian variance.

    Higher variance → sharper image.
    """
    try:
        import cv2  # type: ignore[import-untyped]
    except ImportError:
        return 0.5
    gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY) if image_array.ndim == 3 else image_array
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return float(lap.var())


def _score_brightness(image_array: np.ndarray) -> float:
    """
    Score brightness: ideal is around 120-180 (mid-range).

    Returns a 0-1 score where 1 = ideal brightness.
    """
    try:
        import cv2  # type: ignore[import-untyped]
    except ImportError:
        return 0.5
    gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY) if image_array.ndim == 3 else image_array
    mean_brightness = float(np.mean(gray))
    # Bell curve centred at 140
    ideal = 140.0
    score = max(0.0, 1.0 - abs(mean_brightness - ideal) / ideal)
    return score


def _score_face_presence(image_array: np.ndarray) -> float:
    """
    Quick face presence check using OpenCV's Haar cascade.

    Returns 1.0 if face(s) found, 0.0 otherwise.
    """
    try:
        import cv2  # type: ignore[import-untyped]
    except ImportError:
        return 0.0

    gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY) if image_array.ndim == 3 else image_array
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"  # type: ignore[attr-defined]
    cascade = cv2.CascadeClassifier(cascade_path)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
    return 1.0 if len(faces) > 0 else 0.0


# ── Public API ──────────────────────────────────────────────────────────

@timed(logger_name="processing")
def generate_thumbnails(
    video_path: Path,
    output_dir: Path,
    clip_start: float,
    clip_end: float,
    num_candidates: int = 5,
) -> list[dict[str, Any]]:
    """
    Generate and score thumbnail candidates from a clip range.

    Candidate frames are sampled at evenly-spaced intervals across the
    clip.  Each is scored for sharpness, brightness, and face presence.
    The highest-scoring candidate is marked ``is_selected = True`` and
    exported in both PNG and JPG.

    Args:
        video_path: Source video path.
        output_dir: Directory to write thumbnail images.
        clip_start: Clip start in seconds.
        clip_end: Clip end in seconds.
        num_candidates: Number of frames to sample and evaluate.

    Returns:
        A list of thumbnail dicts::

            [
                {
                    "path": str,
                    "score": float,
                    "format": str,        # "png" or "jpg"
                    "is_selected": bool,
                },
                ...
            ]
    """
    try:
        import cv2  # type: ignore[import-untyped]
    except ImportError:
        logger.error("OpenCV not installed; cannot generate thumbnails.")
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    duration = clip_end - clip_start

    if duration <= 0:
        logger.warning("Invalid clip range for thumbnails.")
        return []

    # ── 1. Determine sample timestamps ──────────────────────────────────
    if num_candidates <= 1:
        sample_times = [clip_start + duration / 2]
    else:
        step = duration / (num_candidates + 1)
        sample_times = [clip_start + step * (i + 1) for i in range(num_candidates)]

    # ── 2. Extract and score each frame ─────────────────────────────────
    scored: list[dict[str, Any]] = []

    for idx, ts in enumerate(sample_times):
        frame_path = output_dir / f"thumb_candidate_{idx:03d}.jpg"
        try:
            extract_frame(video_path, frame_path, ts)
        except RuntimeError as exc:
            logger.warning(f"Frame extraction at {ts:.1f}s failed: {exc}")
            continue

        img = cv2.imread(str(frame_path))
        if img is None:
            continue

        sharpness = _score_sharpness(img)
        brightness = _score_brightness(img)
        face = _score_face_presence(img)

        # Weighted composite score
        composite = 0.4 * min(sharpness / 500.0, 1.0) + 0.3 * brightness + 0.3 * face

        scored.append({
            "path": str(frame_path),
            "score": round(composite, 4),
            "format": "jpg",
            "is_selected": False,
            "timestamp": ts,
            "_img": img,
        })

    if not scored:
        logger.warning("No valid thumbnail candidates produced.")
        return []

    # ── 3. Select best and export formats ───────────────────────────────
    scored.sort(key=lambda x: x["score"], reverse=True)
    scored[0]["is_selected"] = True

    results: list[dict[str, Any]] = []

    for entry in scored:
        img = entry.pop("_img")
        entry.pop("timestamp", None)
        results.append(entry)

        # For the selected thumbnail, also save a PNG version
        if entry["is_selected"]:
            png_path = Path(entry["path"]).with_suffix(".png")
            cv2.imwrite(str(png_path), img)
            results.append({
                "path": str(png_path),
                "score": entry["score"],
                "format": "png",
                "is_selected": True,
            })

    logger.info(
        f"Thumbnails generated: {len(scored)} candidates, "
        f"best score={scored[0]['score']:.3f}"
    )
    return results
