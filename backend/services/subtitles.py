"""
AIClipper Subtitle Generation Service

Generates SRT, WebVTT, and ASS (with word-level highlight) subtitle files
from transcript segment and word data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.utils.logging import get_logger, timed

logger = get_logger("services.subtitles")


# ── Time formatting helpers ─────────────────────────────────────────────

def _format_srt_time(seconds: float) -> str:
    """Format seconds as SRT time: ``HH:MM:SS,mmm``."""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_vtt_time(seconds: float) -> str:
    """Format seconds as VTT time: ``HH:MM:SS.mmm``."""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _format_ass_time(seconds: float) -> str:
    """Format seconds as ASS time: ``H:MM:SS.cc`` (centiseconds)."""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# ── Segment filtering ──────────────────────────────────────────────────

def _filter_segments(
    segments: list[dict[str, Any]],
    clip_start: float,
    clip_end: float | None,
) -> list[dict[str, Any]]:
    """
    Filter segments to those overlapping ``[clip_start, clip_end]`` and
    rebase their timestamps so ``clip_start`` becomes 0.
    """
    filtered: list[dict[str, Any]] = []
    for seg in segments:
        seg_start: float = seg["start"]
        seg_end: float = seg["end"]
        if clip_end is not None and seg_start >= clip_end:
            continue
        if seg_end <= clip_start:
            continue
        # Clamp to window
        adj_start = max(seg_start, clip_start) - clip_start
        adj_end = (min(seg_end, clip_end) if clip_end is not None else seg_end) - clip_start
        new_seg = dict(seg)
        new_seg["start"] = round(adj_start, 3)
        new_seg["end"] = round(adj_end, 3)
        filtered.append(new_seg)
    return filtered


# ── Public API ──────────────────────────────────────────────────────────

@timed(logger_name="processing")
def generate_srt(
    segments: list[dict[str, Any]],
    output_path: Path,
    clip_start: float = 0.0,
    clip_end: float | None = None,
) -> Path:
    """
    Generate an SRT subtitle file from transcript segments.

    Args:
        segments: Transcript segments (each with ``start``, ``end``, ``text``).
        output_path: Destination ``.srt`` file path.
        clip_start: Start time of the clip in the original video (for offset).
        clip_end: End time of the clip in the original video.

    Returns:
        Path to the written SRT file.
    """
    filtered = _filter_segments(segments, clip_start, clip_end)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for idx, seg in enumerate(filtered, start=1):
        lines.append(str(idx))
        lines.append(
            f"{_format_srt_time(seg['start'])} --> {_format_srt_time(seg['end'])}"
        )
        lines.append(seg.get("text", ""))
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"SRT written: {output_path.name} ({len(filtered)} cues)")
    return output_path


@timed(logger_name="processing")
def generate_vtt(
    segments: list[dict[str, Any]],
    output_path: Path,
    clip_start: float = 0.0,
    clip_end: float | None = None,
) -> Path:
    """
    Generate a WebVTT subtitle file from transcript segments.

    Args:
        segments: Transcript segments (each with ``start``, ``end``, ``text``).
        output_path: Destination ``.vtt`` file path.
        clip_start: Start time of the clip in the original video.
        clip_end: End time of the clip in the original video.

    Returns:
        Path to the written VTT file.
    """
    filtered = _filter_segments(segments, clip_start, clip_end)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = ["WEBVTT", ""]
    for idx, seg in enumerate(filtered, start=1):
        lines.append(str(idx))
        lines.append(
            f"{_format_vtt_time(seg['start'])} --> {_format_vtt_time(seg['end'])}"
        )
        lines.append(seg.get("text", ""))
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"VTT written: {output_path.name} ({len(filtered)} cues)")
    return output_path


@timed(logger_name="processing")
def generate_ass_with_highlights(
    words: list[dict[str, Any]],
    output_path: Path,
    clip_start: float = 0.0,
    clip_end: float | None = None,
    font: str = "Arial",
    font_size: int = 24,
    color: str = "#FFFFFF",
    highlight_color: str = "#FFD700",
) -> Path:
    """
    Generate an ASS subtitle file with per-word highlight (karaoke-style).

    Each word is rendered in the default colour, and the currently spoken
    word is shown in ``highlight_color``.  This creates the "bouncing
    word" effect popular on short-form platforms.

    Args:
        words: Word-level timestamps (each with ``word``, ``start``, ``end``).
        output_path: Destination ``.ass`` file path.
        clip_start: Start time of the clip in the original video.
        clip_end: End time of the clip in the original video.
        font: Font family name.
        font_size: Font point size.
        color: Default text colour (hex ``#RRGGBB``).
        highlight_color: Active-word colour (hex ``#RRGGBB``).

    Returns:
        Path to the written ASS file.
    """
    # Filter words to clip range and rebase
    filtered = _filter_segments(words, clip_start, clip_end)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _hex_to_ass_color(hex_color: str) -> str:
        """Convert ``#RRGGBB`` to ASS ``&HBBGGRR&``."""
        h = hex_color.lstrip("#")
        r, g, b = h[0:2], h[2:4], h[4:6]
        return f"&H{b}{g}{r}&"

    primary_color = _hex_to_ass_color(color)
    highlight_ass = _hex_to_ass_color(highlight_color)

    # ASS header
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "WrapStyle: 0\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font},{font_size},{primary_color},&H000000FF,"
        "&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,30,30,60,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )

    # Group words into display lines (≈ 6 words per line)
    words_per_line = 6
    dialogue_lines: list[str] = []

    for chunk_start in range(0, len(filtered), words_per_line):
        chunk = filtered[chunk_start : chunk_start + words_per_line]
        if not chunk:
            continue

        line_start = chunk[0]["start"]
        line_end = chunk[-1]["end"]

        # Build karaoke text: for each word, apply highlight colour during
        # its active time using ASS \kf (smooth karaoke fill) tags.
        text_parts: list[str] = []
        for i, w in enumerate(chunk):
            word_dur_cs = int(round((w["end"] - w["start"]) * 100))
            word_dur_cs = max(word_dur_cs, 1)
            # {\kf<dur>} renders the word with a fill effect
            # {\1c<color>} sets the primary colour for the highlighted word
            text_parts.append(
                f"{{\\kf{word_dur_cs}}}{{\\1c{highlight_ass}}}{w['word']}"
            )

        text = " ".join(text_parts)
        start_str = _format_ass_time(line_start)
        end_str = _format_ass_time(line_end)
        dialogue_lines.append(
            f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}"
        )

    content = header + "\n".join(dialogue_lines) + "\n"
    output_path.write_text(content, encoding="utf-8")

    logger.info(
        f"ASS written: {output_path.name} "
        f"({len(filtered)} words, {len(dialogue_lines)} lines)"
    )
    return output_path
