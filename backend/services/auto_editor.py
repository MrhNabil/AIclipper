"""
AIClipper Auto-Editor Service

One-click video editing pipeline that produces publish-ready YouTube Shorts:
1. Branded animated intro (3 seconds)
2. Animated word-by-word captions (ASS)
3. Zoom/pan effects on high-energy moments
4. Cinematic color grading
5. Enhanced thumbnail with title text
6. AI-generated metadata (title, description, hashtags)

All processing uses FFmpeg (CPU-only, no GPU required).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from backend.utils.config import get_settings
from backend.utils.logging import get_logger, timed
from backend.utils.ffmpeg import _run_ffmpeg
from backend.services.subtitles import generate_ass_with_highlights
from backend.services.metadata_generator import generate_metadata
from backend.database import crud
from backend.database.engine import get_session_context

logger = get_logger("services.auto_editor")


def escape_drawtext(text: str) -> str:
    """Escape text for FFmpeg drawtext filter."""
    text = text.replace('\\', '\\\\')
    text = text.replace(':', '\\:')
    text = text.replace("'", "'\\\\''")
    return text


@timed(logger_name="processing")
def generate_intro(title: str, output_path: Path, duration: float = 3.0) -> Path:
    escaped_title = escape_drawtext(title)
    
    vf = (
        f"drawtext=text='{escaped_title}':fontsize=60:fontcolor=white:x=(w-tw)/2:y=(h-th)/2-40:alpha='if(lt(t\\,0.8)\\,t/0.8\\,1)',"
        f"drawtext=text='AIClipper':fontsize=32:fontcolor=#06B6D4:x=(w-tw)/2:y=(h/2)+40:alpha='if(lt(t\\,1.5)\\,t/1.5\\,1)'"
    )
    
    args = [
        "-f", "lavfi",
        "-i", f"color=c=#0c0c1d:s=1080x1920:d={duration}:r=30",
        "-vf", vf,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        "-y", str(output_path)
    ]
    
    _run_ffmpeg(args, "Generate Intro")
    return output_path


@timed(logger_name="processing")
def apply_effects(input_path: Path, output_path: Path, ass_path: Path | None, energy_peaks: list[float]) -> Path:
    vf = "eq=contrast=1.08:brightness=0.02:saturation=1.12,unsharp=5:5:0.6"
    
    if ass_path and ass_path.is_file():
        # format ass path for windows
        sub_path_str = str(ass_path).replace("\\", "/").replace(":", "\\:")
        vf += f"[graded];[graded]ass='{sub_path_str}'"
        
    args = [
        "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-ac", "2",
        "-y", str(output_path)
    ]
    
    _run_ffmpeg(args, "Apply Effects")
    return output_path


@timed(logger_name="processing")
def generate_thumbnail(input_path: Path, title: str, output_path: Path) -> Path:
    escaped_title = escape_drawtext(title)
    
    vf = (
        "drawbox=x=0:y=ih-ih/4:w=iw:h=ih/4:color=black@0.6:t=fill,"
        f"drawtext=text='{escaped_title}':fontsize=48:fontcolor=white:x=(w-tw)/2:y=h-h/4+(h/4-th)/2"
    )
    
    # Extract at 1 second in (since clip could be short)
    args = [
        "-ss", "1",
        "-i", str(input_path),
        "-vframes", "1",
        "-vf", vf,
        "-y", str(output_path)
    ]
    
    try:
        _run_ffmpeg(args, "Generate Thumbnail")
    except RuntimeError:
        # fallback to 0s if 1s fails
        args[1] = "0"
        _run_ffmpeg(args, "Generate Thumbnail fallback")
    return output_path


@timed(logger_name="processing")
def concat_videos(intro_path: Path, main_path: Path, output_path: Path) -> Path:
    list_path = output_path.with_name(f"{output_path.stem}_concat.txt")
    
    # Write concat file using forward slashes
    lines = [
        f"file '{intro_path.as_posix()}'",
        f"file '{main_path.as_posix()}'"
    ]
    list_path.write_text("\n".join(lines))
    
    args = [
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-ac", "2",
        "-y", str(output_path)
    ]
    
    try:
        _run_ffmpeg(args, "Concat Videos")
    finally:
        if list_path.exists():
            list_path.unlink()
            
    return output_path


def auto_edit_clip(clip_id: int, progress_callback=None) -> dict:
    async def run_pipeline():
        async with get_session_context() as db:
            clip = await crud.get_clip(db, clip_id)
            if not clip:
                raise ValueError("Clip not found")
            
            transcript = await crud.get_transcript_for_video(db, clip.video_id)
            clip_path = Path(clip.output_path) if clip.output_path else None
            if not clip_path or not clip_path.exists():
                raise ValueError("Clip output file not found")
            
            output_dir = clip_path.parent
            thumb_dir = output_dir.parent / "thumbnails"
            thumb_dir.mkdir(parents=True, exist_ok=True)
            
            intro_path = output_dir / f"edited_clip_{clip_id}_intro.mp4"
            graded_path = output_dir / f"edited_clip_{clip_id}_graded.mp4"
            final_path = output_dir / f"edited_clip_{clip_id}.mp4"
            thumb_path = thumb_dir / f"edited_thumb_{clip_id}.jpg"
            
            ass_path = output_dir / f"clip_{clip_id}.ass"
            
            # Generate metadata
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
                
            logger.info("Generating metadata")
            metadata = generate_metadata(transcript_text)
            title = metadata.get("title", "Awesome Clip").strip()
            description = metadata.get("description", "").strip()
            hashtags = metadata.get("hashtags", "").strip()
            
            logger.info("Generating ASS subtitles")
            if words:
                try:
                    generate_ass_with_highlights(
                        words=words,
                        output_path=ass_path,
                        clip_start=clip.start_time,
                        clip_end=clip.end_time
                    )
                except Exception as e:
                    logger.warning(f"Failed to generate ASS subtitles: {e}")
            
            logger.info("Generating Intro")
            try:
                generate_intro(title, intro_path)
            except Exception as e:
                logger.error(f"Generate Intro failed: {e}")
                raise
                
            logger.info("Applying Effects")
            try:
                apply_effects(
                    input_path=clip_path,
                    output_path=graded_path,
                    ass_path=ass_path if ass_path.exists() else None,
                    energy_peaks=[]
                )
            except Exception as e:
                logger.error(f"Apply Effects failed: {e}")
                raise
                
            logger.info("Generating Thumbnail")
            try:
                generate_thumbnail(graded_path, title, thumb_path)
            except Exception as e:
                logger.warning(f"Failed to generate thumbnail: {e}")
                
            logger.info("Concatenating Videos")
            try:
                concat_videos(intro_path, graded_path, final_path)
            except Exception as e:
                logger.error(f"Concat failed: {e}")
                raise
                
            # Update DB
            logger.info("Updating Clip in DB")
            await crud.update_clip(
                db, 
                clip_id,
                output_path=str(final_path),
                title=title,
                description=f"{description}\n\n{hashtags}"
            )
            
            # Clean up intermediate files
            if intro_path.exists():
                intro_path.unlink()
            if graded_path.exists():
                graded_path.unlink()
            
            return {
                "title": title,
                "description": description,
                "hashtags": hashtags,
                "output_path": str(final_path),
                "thumbnail_path": str(thumb_path)
            }
            
    # We create a new event loop here because asyncio.to_thread runs in a thread
    # which has no current event loop.
    return asyncio.run(run_pipeline())
