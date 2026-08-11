"""
AIClipper Copyright Detector Service

Classifies audio segments as speech, music, mixed, or silence to help avoid copyrighted music in clips.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from backend.utils.logging import get_logger, timed

logger = get_logger("services.copyright_detector")


def _safe_normalize(values: np.ndarray) -> np.ndarray:
    """Min-max normalise an array to [0, 1]. Returns zeros on empty/constant input."""
    if values.size == 0:
        return values
    vmin, vmax = float(values.min()), float(values.max())
    if vmax - vmin < 1e-9:
        return np.zeros_like(values)
    return (values - vmin) / (vmax - vmin)


@timed(logger_name="processing")
def detect_copyright_segments(
    audio_path: Path,
    transcript_segments: list[dict[str, Any]] | None = None,
    segment_duration: float = 5.0,
) -> list[dict[str, Any]]:
    """
    Classify audio segments as speech, music, mixed, or silence.

    Uses librosa for acoustic features (RMS energy, spectral flatness,
    zero-crossing rate, spectral centroid) and cross-references with transcript
    segments to robustly detect speech and music.

    Args:
        audio_path: Path to the audio file.
        transcript_segments: Optional list of transcript dicts with 'start', 'end', 'text'.
        segment_duration: Analysis window size in seconds.

    Returns:
        List of dicts containing segment classifications and scores::

            [
                {
                    "start": float,
                    "end": float,
                    "type": "music" | "speech" | "mixed" | "silence",
                    "music_score": float,  # 0-1
                    "speech_score": float, # 0-1
                },
                ...
            ]
    """
    try:
        import librosa  # type: ignore[import-untyped]
    except ImportError:
        logger.warning(
            "librosa is not installed. Copyright detection disabled. "
            "Install with: pip install librosa"
        )
        return []

    logger.info(
        f"Running copyright detection on '{audio_path.name}' "
        f"(segment_duration={segment_duration}s)"
    )

    try:
        y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    except Exception as exc:
        logger.error(f"Failed to load audio for copyright detection: {exc}", exc_info=True)
        return []

    total_duration = float(len(y)) / sr
    if total_duration < 0.1:
        logger.warning("Audio is too short for copyright detection.")
        return []

    hop_length = 512
    frame_length = 2048

    # Extract acoustic features
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    zcr = librosa.feature.zero_crossing_rate(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    flatness = librosa.feature.spectral_flatness(y=y, hop_length=hop_length)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]

    frame_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)

    n_segments = max(1, int(np.ceil(total_duration / segment_duration)))

    seg_energy = np.zeros(n_segments)
    seg_zcr = np.zeros(n_segments)
    seg_flatness = np.zeros(n_segments)
    seg_centroid = np.zeros(n_segments)
    seg_has_transcript = np.zeros(n_segments, dtype=bool)

    for i in range(n_segments):
        t_start = i * segment_duration
        t_end = min((i + 1) * segment_duration, total_duration)
        mask = (frame_times >= t_start) & (frame_times < t_end)

        if mask.sum() == 0:
            continue

        seg_energy[i] = float(np.mean(rms[mask]))
        seg_zcr[i] = float(np.mean(zcr[mask]))
        seg_flatness[i] = float(np.mean(flatness[mask]))
        seg_centroid[i] = float(np.mean(centroid[mask]))

        if transcript_segments:
            for t_seg in transcript_segments:
                overlap = max(t_start, float(t_seg.get("start", 0.0))) < min(t_end, float(t_seg.get("end", 0.0)))
                if overlap and str(t_seg.get("text", "")).strip():
                    seg_has_transcript[i] = True
                    break

    # Normalize features
    energy_norm = _safe_normalize(seg_energy)
    zcr_norm = _safe_normalize(seg_zcr)
    flatness_norm = _safe_normalize(seg_flatness)
    centroid_norm = _safe_normalize(seg_centroid)

    # Calculate raw scores based on logic
    speech_score_raw = np.zeros(n_segments)
    music_score_raw = np.zeros(n_segments)
    
    for i in range(n_segments):
        # Speech: high zcr + moderate energy + has transcript
        speech_raw = zcr_norm[i] * 0.4 + energy_norm[i] * 0.2 + (0.4 if seg_has_transcript[i] else 0.0)
        speech_score_raw[i] = speech_raw
        
        # Music: high flatness + low zcr + no speech + sustained energy
        music_raw = flatness_norm[i] * 0.4 + (1.0 - zcr_norm[i]) * 0.3 + energy_norm[i] * 0.3
        if not seg_has_transcript[i]:
            music_raw += 0.2
        music_score_raw[i] = music_raw

    speech_scores = _safe_normalize(speech_score_raw)
    music_scores = _safe_normalize(music_score_raw)

    results: list[dict[str, Any]] = []

    for i in range(n_segments):
        t_start = round(i * segment_duration, 3)
        t_end = round(min((i + 1) * segment_duration, total_duration), 3)

        # Silence: very low RMS energy
        is_silence = seg_energy[i] < 1e-4 or energy_norm[i] < 0.05
        
        music_score = float(music_scores[i])
        speech_score = float(speech_scores[i])
        
        if is_silence:
            seg_type = "silence"
            music_score = 0.0
            speech_score = 0.0
        elif seg_has_transcript[i]:
            if music_score > 0.7:
                seg_type = "mixed"
            else:
                seg_type = "speech"
        else:
            if music_score > speech_score:
                seg_type = "music"
            else:
                seg_type = "mixed"

        results.append({
            "start": t_start,
            "end": t_end,
            "type": seg_type,
            "music_score": round(music_score, 4),
            "speech_score": round(speech_score, 4),
        })

    logger.info(f"Copyright detection complete: {n_segments} segments analyzed.")
    return results


def get_copyright_score_for_range(segments: list[dict[str, Any]], start: float, end: float) -> float:
    """
    Calculate the average music score for a specific time range.

    Args:
        segments: The list of segments returned by detect_copyright_segments.
        start: Start time in seconds.
        end: End time in seconds.

    Returns:
        Average music_score (0-1) for the requested range.
    """
    if not segments or start >= end:
        return 0.0

    total_score = 0.0
    total_duration = 0.0

    for seg in segments:
        seg_start = float(seg.get("start", 0.0))
        seg_end = float(seg.get("end", 0.0))

        # Calculate overlap
        overlap_start = max(start, seg_start)
        overlap_end = min(end, seg_end)
        overlap = overlap_end - overlap_start

        if overlap > 0:
            total_score += float(seg.get("music_score", 0.0)) * overlap
            total_duration += overlap

    if total_duration > 0:
        return total_score / total_duration

    return 0.0
