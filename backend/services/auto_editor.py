"""
AIClipper Auto-Editor Service

One-click video editing pipeline that produces publish-ready YouTube Shorts:
1. Branded animated intro (3 seconds)
2. Animated word-by-word captions (ASS)
3. Cinematic color grading
4. Enhanced thumbnail with title text
5. AI-generated metadata (title, description, hashtags)

All processing uses FFmpeg (CPU-only, no GPU required).
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import shutil
from pathlib import Path
from typing import Any

from backend.utils.config import get_settings
from backend.utils.logging import get_logger, timed
from backend.services.subtitles import generate_ass_with_highlights
from backend.services.metadata_generator import generate_metadata
from backend.database import crud
from backend.database.engine import get_session_context

logger = get_logger("services.auto_editor")

# Windows font path
FONT_FILE = "C:/Windows/Fonts/arial.ttf"


def _get_creation_flags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def _run_ffmpeg_safe(args: list[str], description: str = "FFmpeg") -> None:
    settings = get_settings()
    cmd = [settings.ffmpeg_path] + args
    logger.debug(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600,
            creationflags=_get_creation_flags(),
        )
        if result.returncode != 0:
            real_errors = [
                line for line in (result.stderr or "").split("\n")
                if any(kw in line.lower() for kw in ["error", "invalid", "no such", "failed"])
                and "fontconfig" not in line.lower()
            ]
            if real_errors:
                logger.error(f"{description}: {'; '.join(real_errors[:3])}")
                raise RuntimeError(f"{description}: {'; '.join(real_errors[:3])}")
            else:
                logger.warning(f"{description} non-zero exit but no real errors")
    except FileNotFoundError:
        raise RuntimeError(f"FFmpeg not found at '{settings.ffmpeg_path}'.")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{description} timed out.")


def _escape_drawtext(text: str) -> str:
    text = text.replace("\\", "").replace("'", "").replace('"', "")
    text = text.replace(":", " ").replace(";", " ").replace("%", " pct")
    return text[:57] + "..." if len(text) > 60 else text


@timed(logger_name="processing")
def generate_intro(title: str, output_path: Path, duration: float = 3.0) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    safe_title = _escape_drawtext(title)
    fe = FONT_FILE.replace(":", "\\:")
    vf = (
        f"drawtext=fontfile='{fe}':text='{safe_title}':fontsize=56:fontcolor=white"
        f":x=(w-tw)/2:y=(h-th)/2-40:borderw=2:bordercolor=black,"
        f"drawtext=fontfile='{fe}':text='AIClipper':fontsize=30:fontcolor=#06B6D4"
        f":x=(w-tw)/2:y=(h/2)+40:borderw=1:bordercolor=black"
    )
    args = [
        "-f", "lavfi", "-i", f"color=c=#0c0c1d:s=1080x1920:d={duration}:r=30",
        "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-t", str(duration), "-y", str(output_path.resolve())
    ]
    _run_ffmpeg_safe(args, "Generate Intro")
    if not output_path.exists() or output_path.stat().st_size < 100:
        raise RuntimeError("Intro generation produced no output")
    logger.info(f"Intro generated: {output_path.stat().st_size} bytes")
    return output_path


@timed(logger_name="processing")
def apply_effects(input_path: Path, output_path: Path, ass_path: Path | None, energy_peaks: list[float]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vf_parts = ["eq=contrast=1.08:brightness=0.02:saturation=1.12", "unsharp=5:5:0.6"]
    if ass_path and ass_path.is_file():
        sub_str = ass_path.as_posix().replace(":", "\\:")
        vf_parts.append(f"ass='{sub_str}'")
    vf = ",".join(vf_parts)
    args = [
        "-i", str(input_path.resolve()), "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-ac", "2", "-y", str(output_path.resolve())
    ]
    _run_ffmpeg_safe(args, "Apply Effects")
    if not output_path.exists() or output_path.stat().st_size < 100:
        raise RuntimeError("Effects pass produced no output")
    logger.info(f"Effects applied: {output_path.stat().st_size} bytes")
    return output_path


@timed(logger_name="processing")
def generate_thumbnail(input_path: Path, title: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    safe_title = _escape_drawtext(title)
    fe = FONT_FILE.replace(":", "\\:")
    vf = (
        "drawbox=x=0:y=ih-ih/4:w=iw:h=ih/4:color=black@0.6:t=fill,"
        f"drawtext=fontfile='{fe}':text='{safe_title}':fontsize=44:fontcolor=white"
        f":x=(w-tw)/2:y=h-h/4+(h/4-th)/2:borderw=2:bordercolor=black"
    )
    args = ["-ss", "1", "-i", str(input_path.resolve()), "-vframes", "1", "-vf", vf, "-q:v", "2", "-y", str(output_path.resolve())]
    try:
        _run_ffmpeg_safe(args, "Generate Thumbnail")
    except RuntimeError:
        args2 = ["-ss", "0", "-i", str(input_path.resolve()), "-vframes", "1", "-q:v", "2", "-y", str(output_path.resolve())]
        _run_ffmpeg_safe(args2, "Thumbnail fallback")
    if output_path.exists():
        logger.info(f"Thumbnail: {output_path.stat().st_size} bytes")
    return output_path


@timed(logger_name="processing")
def concat_videos(intro_path: Path, main_path: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Resolve to absolute paths so FFmpeg can always find files
    abs_intro = intro_path.resolve()
    abs_main = main_path.resolve()
    abs_output = output_path.resolve()
    list_path = abs_output.with_name(f"{abs_output.stem}_concat.txt")

    list_path.write_text(
        f"file '{abs_intro.as_posix()}'\nfile '{abs_main.as_posix()}'"
    )
    args = [
        "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-ac", "2", "-y", str(abs_output)
    ]
    try:
        _run_ffmpeg_safe(args, "Concat Videos")
    finally:
        if list_path.exists():
            list_path.unlink()
    if not output_path.exists() or output_path.stat().st_size < 100:
        raise RuntimeError("Concat produced no output")
    logger.info(f"Final video: {output_path.stat().st_size} bytes")
    return output_path


def auto_edit_clip(clip_id: int, progress_callback=None) -> dict:
    async def run_pipeline():
        async with get_session_context() as db:
            clip = await crud.get_clip(db, clip_id)
            if not clip:
                raise ValueError("Clip not found")
            clip_path = Path(clip.output_path) if clip.output_path else None
            if not clip_path or not clip_path.exists():
                raise ValueError("Clip output file not found")
            transcript = await crud.get_transcript_for_video(db, clip.video_id)

            output_dir = clip_path.parent
            thumb_dir = output_dir.parent / "thumbnails"
            thumb_dir.mkdir(parents=True, exist_ok=True)

            intro_path = output_dir / f"edited_clip_{clip_id}_intro.mp4"
            graded_path = output_dir / f"edited_clip_{clip_id}_graded.mp4"
            final_path = output_dir / f"edited_clip_{clip_id}.mp4"
            thumb_path = thumb_dir / f"edited_thumb_{clip_id}.jpg"
            ass_path = output_dir / f"clip_{clip_id}.ass"

            # Step 1: Metadata
            transcript_text = ""
            words = []
            if transcript and transcript.word_timestamps_json:
                words = transcript.word_timestamps_json
                transcript_text = " ".join([
                    w.get("word", "") for w in words
                    if clip.start_time <= w.get("start", 0) <= clip.end_time
                ])
            elif transcript and transcript.full_text:
                transcript_text = transcript.full_text
            if not transcript_text:
                transcript_text = "Check out this amazing short clip!"

            logger.info("Step 1: Generating metadata...")
            metadata = generate_metadata(transcript_text)
            title = metadata.get("title", "Awesome Clip").strip()
            description = metadata.get("description", "").strip()
            hashtags = metadata.get("hashtags", "").strip()
            keywords = metadata.get("keywords", "").strip()

            # Step 2: ASS captions
            logger.info("Step 2: Generating captions...")
            if words:
                try:
                    generate_ass_with_highlights(
                        words=words, output_path=ass_path,
                        clip_start=clip.start_time, clip_end=clip.end_time,
                    )
                except Exception as e:
                    logger.warning(f"ASS generation failed: {e}")

            # Step 3: Intro
            logger.info("Step 3: Generating intro...")
            intro_ok = False
            try:
                generate_intro(title, intro_path)
                intro_ok = True
            except Exception as e:
                logger.warning(f"Intro failed, continuing without: {e}")

            # Step 4: Effects
            logger.info("Step 4: Applying effects...")
            apply_effects(
                input_path=clip_path, output_path=graded_path,
                ass_path=ass_path if ass_path.exists() else None, energy_peaks=[],
            )

            # Step 5: Thumbnail
            logger.info("Step 5: Generating thumbnail...")
            try:
                generate_thumbnail(graded_path, title, thumb_path)
            except Exception as e:
                logger.warning(f"Thumbnail failed: {e}")

            # Step 6: Concat
            if intro_ok and intro_path.exists():
                logger.info("Step 6: Concatenating intro + clip...")
                concat_videos(intro_path, graded_path, final_path)
            else:
                logger.info("Step 6: Using graded clip as final...")
                shutil.move(str(graded_path), str(final_path))

            # Step 7: Update DB
            logger.info("Step 7: Updating database...")
            await crud.update_clip(db, clip_id,
                output_path=str(final_path), title=title,
                description=f"{description}\n\n{hashtags}",
                hashtags=hashtags, keywords=keywords,
            )

            # Cleanup
            for p in [intro_path, graded_path]:
                if p and Path(p).exists():
                    try: Path(p).unlink()
                    except: pass

            logger.info(f"Auto-edit complete for clip {clip_id}")
            return {
                "title": title, "description": description,
                "hashtags": hashtags, "output_path": str(final_path),
                "thumbnail_path": str(thumb_path) if thumb_path.exists() else None,
            }

    return asyncio.run(run_pipeline())
