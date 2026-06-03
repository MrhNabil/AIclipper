"""
AIClipper Face & Subject Tracking Service

Detects faces via the MediaPipe Tasks Vision API, computes 9:16 crop
coordinates centred on the primary face, and smooths the crop path with
an exponential moving average.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.utils.config import get_settings
from backend.utils.logging import get_logger, timed

logger = get_logger("services.face_tracking")


def _clamp(value: int, lo: int, hi: int) -> int:
    """Clamp *value* to the range [lo, hi]."""
    return max(lo, min(value, hi))


def _compute_vertical_crop(
    face_cx: int,
    face_cy: int,
    frame_w: int,
    frame_h: int,
) -> tuple[int, int, int, int]:
    """
    Compute a 9:16 crop rectangle centred on the face.

    The crop is as large as the source frame allows while maintaining
    a 9:16 aspect ratio.

    Args:
        face_cx: Face centre x.
        face_cy: Face centre y.
        frame_w: Source frame width.
        frame_h: Source frame height.

    Returns:
        (crop_x, crop_y, crop_w, crop_h)
    """
    # Target aspect ratio 9:16
    target_ratio = 9.0 / 16.0

    # Start with full height, derive width
    crop_h = frame_h
    crop_w = int(crop_h * target_ratio)

    if crop_w > frame_w:
        # Frame is narrower than 9:16 — fit to width instead
        crop_w = frame_w
        crop_h = int(crop_w / target_ratio)

    # Centre crop on the face, but stay within frame bounds
    crop_x = _clamp(face_cx - crop_w // 2, 0, frame_w - crop_w)
    crop_y = _clamp(face_cy - crop_h // 2, 0, frame_h - crop_h)

    return crop_x, crop_y, crop_w, crop_h


@timed(logger_name="processing")
def track_faces(
    video_path: Path,
    sample_every_n: int | None = None,
) -> list[dict[str, Any]]:
    """
    Detect faces across sampled video frames and compute smoothed 9:16 crops.

    Uses the **MediaPipe Tasks Vision API** (``FaceDetector``) with
    ``RunningMode.VIDEO`` and monotonically increasing timestamps.

    Args:
        video_path: Path to the source video file.
        sample_every_n: Process every N-th frame.  Defaults to the value
            in ``Settings.face_sample_every_n_frames``.

    Returns:
        A chronological list of crop-position dicts::

            [
                {
                    "time": float,          # seconds into the video
                    "crop_x": int,
                    "crop_y": int,
                    "crop_w": int,
                    "crop_h": int,
                    "face_visible": bool,
                    "num_faces": int,
                },
                ...
            ]

        Returns an empty list if MediaPipe or OpenCV is not installed, or
        if the model file is missing.
    """
    settings = get_settings()
    if sample_every_n is None:
        sample_every_n = settings.face_sample_every_n_frames

    # ── 1. Import dependencies ──────────────────────────────────────────
    try:
        import cv2  # type: ignore[import-untyped]
        import mediapipe as mp  # type: ignore[import-untyped]
        from mediapipe.tasks import python as mp_python  # type: ignore[import-untyped]
        from mediapipe.tasks.python import vision as mp_vision  # type: ignore[import-untyped]
    except ImportError as exc:
        logger.error(f"Missing dependency for face tracking: {exc}")
        return []

    # ── 2. Locate model file ────────────────────────────────────────────
    model_path: Path = settings.mediapipe_model_path
    if not model_path.exists():
        logger.warning(
            f"MediaPipe model not found at '{model_path}'. "
            "Face tracking will be skipped.  Download the model from "
            "https://storage.googleapis.com/mediapipe-models/face_detector/"
            "blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
        )
        return []

    # ── 3. Open video ───────────────────────────────────────────────────
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.error(f"Cannot open video: {video_path}")
        return []

    fps: float = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    logger.info(
        f"Tracking faces in '{video_path.name}': "
        f"{frame_w}x{frame_h} @ {fps:.1f}fps, "
        f"~{total_frames} frames, sampling every {sample_every_n}"
    )

    # ── 4. Create MediaPipe FaceDetector ────────────────────────────────
    base_options = mp_python.BaseOptions(model_asset_path=str(model_path))
    options = mp_vision.FaceDetectorOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.VIDEO,
    )

    results: list[dict[str, Any]] = []

    # EMA state for smoothing
    ema_alpha = 0.3
    ema_cx: float | None = None
    ema_cy: float | None = None

    try:
        with mp_vision.FaceDetector.create_from_options(options) as detector:
            frame_idx = 0
            last_ts_ms = -1  # ensure monotonically increasing timestamps

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % sample_every_n != 0:
                    frame_idx += 1
                    continue

                timestamp_ms = int(round((frame_idx / fps) * 1000))
                # MediaPipe requires strictly increasing timestamps
                if timestamp_ms <= last_ts_ms:
                    timestamp_ms = last_ts_ms + 1
                last_ts_ms = timestamp_ms

                # Convert BGR → RGB for MediaPipe
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB, data=rgb_frame
                )

                detection_result = detector.detect_for_video(
                    mp_image, timestamp_ms
                )

                num_faces = len(detection_result.detections)
                face_visible = num_faces > 0
                time_s = round(frame_idx / fps, 3)

                if face_visible:
                    # Use the first (most confident) detection
                    det = detection_result.detections[0]
                    bbox = det.bounding_box
                    face_cx = bbox.origin_x + bbox.width // 2
                    face_cy = bbox.origin_y + bbox.height // 2

                    # Apply EMA smoothing
                    if ema_cx is None:
                        ema_cx = float(face_cx)
                        ema_cy = float(face_cy)
                    else:
                        ema_cx = ema_alpha * face_cx + (1 - ema_alpha) * ema_cx
                        ema_cy = ema_alpha * face_cy + (1 - ema_alpha) * ema_cy

                    crop_x, crop_y, crop_w, crop_h = _compute_vertical_crop(
                        int(ema_cx), int(ema_cy), frame_w, frame_h  # type: ignore[arg-type]
                    )
                else:
                    # No face — use centre of frame (or previous EMA)
                    cx = int(ema_cx) if ema_cx is not None else frame_w // 2
                    cy = int(ema_cy) if ema_cy is not None else frame_h // 2
                    crop_x, crop_y, crop_w, crop_h = _compute_vertical_crop(
                        cx, cy, frame_w, frame_h
                    )

                results.append({
                    "time": time_s,
                    "crop_x": crop_x,
                    "crop_y": crop_y,
                    "crop_w": crop_w,
                    "crop_h": crop_h,
                    "face_visible": face_visible,
                    "num_faces": num_faces,
                })

                frame_idx += 1

    except Exception as exc:
        logger.error(f"Face tracking error: {exc}", exc_info=True)
    finally:
        cap.release()

    logger.info(
        f"Face tracking complete: {len(results)} sample points, "
        f"{sum(1 for r in results if r['face_visible'])} with faces"
    )
    return results
