"""
AIClipper Transcription Service

Extracts audio from video, runs speech-to-text via pywhispercpp, and returns
structured transcript data with segment- and word-level timestamps.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from backend.utils.config import get_settings
from backend.utils.ffmpeg import extract_audio
from backend.utils.logging import get_logger, timed

logger = get_logger("services.transcription")


def _interpolate_word_timestamps(
    text: str,
    start_ms: int,
    end_ms: int,
) -> list[dict[str, Any]]:
    """
    Split segment text into words and linearly interpolate timestamps.

    Args:
        text: The segment's text string.
        start_ms: Segment start in milliseconds.
        end_ms: Segment end in milliseconds.

    Returns:
        List of word dicts: ``{"word": str, "start": float, "end": float}``
        where times are in **seconds**.
    """
    words = text.split()
    if not words:
        return []

    total_chars = sum(len(w) for w in words)
    if total_chars == 0:
        return []

    duration_ms = end_ms - start_ms
    cursor_ms = start_ms
    result: list[dict[str, Any]] = []

    for word in words:
        word_duration = int(duration_ms * (len(word) / total_chars))
        word_end = cursor_ms + word_duration
        result.append({
            "word": word,
            "start": round(cursor_ms / 1000.0, 3),
            "end": round(word_end / 1000.0, 3),
        })
        cursor_ms = word_end

    # Snap last word's end to segment boundary
    if result:
        result[-1]["end"] = round(end_ms / 1000.0, 3)

    return result


@timed(logger_name="processing")
def transcribe_video(
    video_path: Path,
    language: str = "auto",
    model_name: str | None = None,
) -> dict[str, Any]:
    """
    Transcribe a video file and return structured transcript data.

    The function extracts a 16 kHz mono WAV from the video, runs Whisper
    inference via *pywhispercpp*, and assembles segment-level plus
    approximate word-level timestamps.

    Args:
        video_path: Path to the source video file.
        language: ISO language code or ``"auto"`` for auto-detection.
        model_name: Whisper model name (e.g. ``"small.en"``).  Falls back to
            the value in ``Settings.whisper_model``.

    Returns:
        A dict with the following keys::

            {
                "language": str,
                "segments": [
                    {"start": float, "end": float, "text": str}
                ],
                "full_text": str,
                "words": [
                    {"word": str, "start": float, "end": float}
                ],
            }

    Raises:
        RuntimeError: If pywhispercpp is not installed or audio extraction fails.
    """
    settings = get_settings()
    if model_name is None:
        model_name = settings.whisper_model

    # ── 1. Try to import pywhispercpp ───────────────────────────────────
    try:
        from pywhispercpp.model import Model as WhisperModel  # type: ignore[import-untyped]
    except ImportError:
        logger.error(
            "pywhispercpp is not installed. "
            "Install it with: pip install pywhispercpp"
        )
        raise RuntimeError(
            "pywhispercpp is not installed. "
            "Install it with: pip install pywhispercpp"
        )

    # ── 2. Extract audio to a temp WAV ──────────────────────────────────
    temp_dir = Path(tempfile.mkdtemp(prefix="aiclipper_audio_"))
    audio_path = temp_dir / "audio_16k.wav"
    try:
        extract_audio(video_path, audio_path, sample_rate=16000, mono=True)
        logger.info(f"Audio extracted to {audio_path}")

        # ── 3. Run Whisper inference ────────────────────────────────────
        n_threads = settings.whisper_threads
        logger.info(
            f"Running Whisper model='{model_name}' threads={n_threads} "
            f"language='{language}'"
        )

        model = WhisperModel(model_name, n_threads=n_threads)
        raw_segments = model.transcribe(str(audio_path))

        # ── 4. Build structured result ──────────────────────────────────
        segments: list[dict[str, Any]] = []
        all_words: list[dict[str, Any]] = []
        full_text_parts: list[str] = []

        for seg in raw_segments:
            start_s = round(seg.t0 / 1000.0, 3)
            end_s = round(seg.t1 / 1000.0, 3)
            text = seg.text.strip()
            if not text:
                continue

            segments.append({
                "start": start_s,
                "end": end_s,
                "text": text,
            })
            full_text_parts.append(text)

            # Approximate word-level timestamps
            word_ts = _interpolate_word_timestamps(text, seg.t0, seg.t1)
            all_words.extend(word_ts)

        detected_language = language if language != "auto" else "en"

        result: dict[str, Any] = {
            "language": detected_language,
            "segments": segments,
            "full_text": " ".join(full_text_parts),
            "words": all_words,
        }

        logger.info(
            f"Transcription complete: {len(segments)} segments, "
            f"{len(all_words)} words, language='{detected_language}'"
        )
        return result

    finally:
        # ── 5. Clean up temp audio ──────────────────────────────────────
        try:
            if audio_path.exists():
                audio_path.unlink()
            temp_dir.rmdir()
        except OSError as exc:
            logger.warning(f"Temp cleanup failed: {exc}")
