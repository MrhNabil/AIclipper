"""
AIClipper Clip Scoring Engine

Slides a window across the video timeline, scores each candidate clip on
multiple dimensions (emotion, dialogue, scene changes, audio energy, face
presence), then applies non-maximum suppression to pick the best
non-overlapping clips.
"""

from __future__ import annotations

from typing import Any

from backend.utils.config import get_settings
from backend.utils.logging import get_logger, timed

logger = get_logger("services.clip_scoring")

# Default scoring weights (mirrors ScoringWeights in config)
_DEFAULT_WEIGHTS: dict[str, float] = {
    "emotion": 0.25,
    "dialogue": 0.20,
    "scene_change": 0.20,
    "audio": 0.20,
    "face": 0.15,
}


def _items_in_window(
    items: list[dict[str, Any]],
    win_start: float,
    win_end: float,
    start_key: str = "start",
    end_key: str | None = "end",
) -> list[dict[str, Any]]:
    """Return items whose time span overlaps ``[win_start, win_end)``."""
    result: list[dict[str, Any]] = []
    for item in items:
        item_start = item[start_key]
        item_end = item.get(end_key, item_start) if end_key else item_start
        if item_end > win_start and item_start < win_end:
            result.append(item)
    return result


def _face_items_in_window(
    face_data: list[dict[str, Any]],
    win_start: float,
    win_end: float,
) -> list[dict[str, Any]]:
    """Return face-tracking data points inside the window."""
    return [f for f in face_data if win_start <= f["time"] < win_end]


# ── Scoring helpers ─────────────────────────────────────────────────────

def _emotion_score(audio_segments: list[dict[str, Any]], win_start: float, win_end: float) -> float:
    """Average emotion_intensity from audio segments in window."""
    segs = _items_in_window(audio_segments, win_start, win_end)
    if not segs:
        return 0.0
    return sum(s.get("emotion_intensity", 0.0) for s in segs) / len(segs)


def _dialogue_score(
    transcript: dict[str, Any],
    win_start: float,
    win_end: float,
    global_max_words: int,
) -> float:
    """Word density in window relative to the densest window."""
    segments = transcript.get("segments", [])
    segs = _items_in_window(segments, win_start, win_end)
    word_count = sum(len(s.get("text", "").split()) for s in segs)
    if global_max_words <= 0:
        return 0.0
    return min(word_count / global_max_words, 1.0)


def _scene_change_score(
    scenes: list[dict[str, Any]],
    win_start: float,
    win_end: float,
    max_transitions: int,
) -> float:
    """Number of scene transitions in window, normalised."""
    count = 0
    for s in scenes:
        # A transition happens at the scene start boundary
        if win_start < s["start"] < win_end:
            count += 1
    if max_transitions <= 0:
        return 0.0
    return min(count / max_transitions, 1.0)


def _audio_score(audio_segments: list[dict[str, Any]], win_start: float, win_end: float) -> float:
    """Average energy_score from audio segments in window."""
    segs = _items_in_window(audio_segments, win_start, win_end)
    if not segs:
        return 0.0
    return sum(s.get("energy_score", 0.0) for s in segs) / len(segs)


def _face_score(face_data: list[dict[str, Any]], win_start: float, win_end: float) -> float:
    """Percentage of sampled frames with face_visible."""
    pts = _face_items_in_window(face_data, win_start, win_end)
    if not pts:
        return 0.0
    return sum(1 for p in pts if p.get("face_visible")) / len(pts)


# ── Pre-computation for normalisation ───────────────────────────────────

def _compute_max_words_in_window(
    transcript: dict[str, Any],
    video_duration: float,
    window_size: float,
    step: float,
) -> int:
    """Scan all windows and return the max word count (for normalisation)."""
    segments = transcript.get("segments", [])
    max_words = 0
    pos = 0.0
    while pos + window_size <= video_duration + 0.01:
        segs = _items_in_window(segments, pos, pos + window_size)
        wc = sum(len(s.get("text", "").split()) for s in segs)
        if wc > max_words:
            max_words = wc
        pos += step
    return max(max_words, 1)


def _compute_max_transitions_in_window(
    scenes: list[dict[str, Any]],
    video_duration: float,
    window_size: float,
    step: float,
) -> int:
    """Scan all windows and return the max transition count."""
    max_count = 0
    pos = 0.0
    while pos + window_size <= video_duration + 0.01:
        count = sum(1 for s in scenes if pos < s["start"] < pos + window_size)
        if count > max_count:
            max_count = count
        pos += step
    return max(max_count, 1)


# ── Non-maximum suppression ────────────────────────────────────────────

def _non_maximum_suppression(
    candidates: list[dict[str, Any]],
    max_clips: int,
    min_gap: float,
) -> list[dict[str, Any]]:
    """Select top-scoring clips ensuring a minimum time gap between them."""
    # Sort descending by score
    sorted_cands = sorted(candidates, key=lambda c: c["total_score"], reverse=True)
    selected: list[dict[str, Any]] = []

    for cand in sorted_cands:
        if len(selected) >= max_clips:
            break
        # Check gap to every already-selected clip
        overlaps = False
        for sel in selected:
            gap = max(
                cand["start"] - sel["end"],
                sel["start"] - cand["end"],
            )
            if gap < min_gap:
                overlaps = True
                break
        if not overlaps:
            selected.append(cand)

    # Return sorted by start time for intuitive ordering
    return sorted(selected, key=lambda c: c["start"])


# ── Public API ──────────────────────────────────────────────────────────

@timed(logger_name="processing")
def score_clips(
    video_duration: float,
    transcript: dict[str, Any],
    scenes: list[dict[str, Any]],
    audio_segments: list[dict[str, Any]],
    face_data: list[dict[str, Any]],
    clip_durations: list[int] | None = None,
    weights: dict[str, float] | None = None,
    max_clips: int = 10,
    min_gap: float = 10.0,
) -> list[dict[str, Any]]:
    """
    Score and select the best candidate clips from a video.

    A sliding window (step = 1 s) is swept across the timeline for each
    requested clip duration.  Per-window scores are computed for five
    dimensions, weighted, and summed.  Non-maximum suppression then picks
    the top non-overlapping clips.

    Args:
        video_duration: Total video length in seconds.
        transcript: Transcript dict as returned by ``transcribe_video()``.
        scenes: Scene list as returned by ``detect_scenes()``.
        audio_segments: Audio analysis list from ``analyze_audio()``.
        face_data: Face tracking list from ``track_faces()``.
        clip_durations: Desired clip lengths in seconds (default from config).
        weights: Scoring-dimension weights dict.
        max_clips: Maximum clips to return.
        min_gap: Minimum gap (seconds) between selected clips.

    Returns:
        A list of scored clip dicts, sorted by start time::

            [
                {
                    "start": float,
                    "end": float,
                    "duration": float,
                    "total_score": float,
                    "breakdown": {
                        "emotion": float,
                        "dialogue": float,
                        "scene_change": float,
                        "audio": float,
                        "face": float,
                    },
                },
                ...
            ]
    """
    settings = get_settings()
    if clip_durations is None:
        clip_durations = settings.clip_durations
    if weights is None:
        sw = settings.scoring_weights
        weights = {
            "emotion": sw.emotion,
            "dialogue": sw.dialogue,
            "scene_change": sw.scene_change,
            "audio": sw.audio,
            "face": sw.face,
        }

    step = 1.0  # sliding-window step (seconds)
    all_candidates: list[dict[str, Any]] = []

    for dur in clip_durations:
        if dur > video_duration:
            continue

        # Pre-compute normalisation ceilings for this window size
        max_words = _compute_max_words_in_window(
            transcript, video_duration, float(dur), step
        )
        max_transitions = _compute_max_transitions_in_window(
            scenes, video_duration, float(dur), step
        )

        pos = 0.0
        while pos + dur <= video_duration + 0.01:
            win_start = pos
            win_end = pos + dur

            emo = _emotion_score(audio_segments, win_start, win_end)
            dia = _dialogue_score(transcript, win_start, win_end, max_words)
            sc = _scene_change_score(scenes, win_start, win_end, max_transitions)
            aud = _audio_score(audio_segments, win_start, win_end)
            fac = _face_score(face_data, win_start, win_end)

            total = (
                weights["emotion"] * emo
                + weights["dialogue"] * dia
                + weights["scene_change"] * sc
                + weights["audio"] * aud
                + weights["face"] * fac
            )

            all_candidates.append({
                "start": round(win_start, 3),
                "end": round(win_end, 3),
                "duration": dur,
                "total_score": round(total, 4),
                "breakdown": {
                    "emotion": round(emo, 4),
                    "dialogue": round(dia, 4),
                    "scene_change": round(sc, 4),
                    "audio": round(aud, 4),
                    "face": round(fac, 4),
                },
            })
            pos += step

    # Non-maximum suppression
    selected = _non_maximum_suppression(all_candidates, max_clips, min_gap)

    logger.info(
        f"Clip scoring complete: {len(all_candidates)} candidates evaluated, "
        f"{len(selected)} clips selected"
    )
    return selected
