"""
AIClipper Workflow Pipeline Orchestrator

Runs the full automated processing pipeline for a video:
  Ingestion → Transcription → Scene Detection → Audio Analysis
  → Face Tracking → Clip Scoring → Clip Generation → Subtitles
  → Metadata → Thumbnails
"""

from __future__ import annotations

import asyncio
import traceback
from pathlib import Path
from typing import Any, Callable

from backend.database import crud
from backend.database.engine import get_session_context
from backend.database.models import ClipStatus, SubtitleFormat, VideoStatus
from backend.utils.config import get_settings
from backend.utils.logging import get_logger, timed

logger = get_logger("processing.pipeline")


async def _update_progress(
    video_id: int,
    progress: int,
    step: str,
    callback: Callable | None = None,
) -> None:
    """Update DB progress and invoke optional callback."""
    async with get_session_context() as session:
        await crud.update_video_status(
            session, video_id,
            status=VideoStatus.PROCESSING,
            progress=progress,
            step=step,
        )
    if callback:
        try:
            callback(progress, step)
        except Exception:
            pass
    logger.info(f"Video {video_id}: [{progress}%] {step}")


@timed(logger_name="processing")
async def process_video_pipeline(
    video_id: int,
    progress_callback: Callable[[int, str], Any] | None = None,
) -> dict[str, Any]:
    """
    Run the full processing pipeline on a video.

    Args:
        video_id: Database ID of the video to process
        progress_callback: Optional callback(progress_pct, step_name) for real-time updates

    Returns:
        dict with pipeline results summary
    """
    settings = get_settings()
    results: dict[str, Any] = {"video_id": video_id, "steps": {}, "clips_generated": 0}

    # --- Fetch video info ---
    async with get_session_context() as session:
        video = await crud.get_video(session, video_id)
        if not video:
            raise ValueError(f"Video {video_id} not found")
        video_path = Path(video.filepath)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        await crud.update_video_status(
            session, video_id, status=VideoStatus.PROCESSING, progress=0, step="Initializing"
        )

    try:
        # =====================================================================
        # Step 1: Transcription (0-20%)
        # =====================================================================
        await _update_progress(video_id, 2, "Transcribing audio...", progress_callback)
        transcript_data = {}
        try:
            from backend.services.transcription import transcribe_video
            transcript_data = transcribe_video(
                video_path,
                language=settings.whisper_language,
                model_name=settings.whisper_model,
            )
            async with get_session_context() as session:
                await crud.create_transcript(
                    session,
                    video_id=video_id,
                    language=transcript_data.get("language", "en"),
                    content_json=transcript_data.get("segments", []),
                    word_timestamps_json=transcript_data.get("words", []),
                    full_text=transcript_data.get("full_text", ""),
                )
            results["steps"]["transcription"] = "success"
        except Exception as e:
            logger.error(f"Transcription failed: {e}\n{traceback.format_exc()}")
            results["steps"]["transcription"] = f"failed: {str(e)}"
            transcript_data = {"segments": [], "words": [], "full_text": ""}

        await _update_progress(video_id, 20, "Transcription complete", progress_callback)

        # =====================================================================
        # Step 2: Scene Detection (20-35%)
        # =====================================================================
        await _update_progress(video_id, 22, "Detecting scenes...", progress_callback)
        scenes_data: list[dict] = []
        try:
            from backend.services.scene_detection import detect_scenes
            scenes_data = detect_scenes(video_path)
            async with get_session_context() as session:
                await crud.create_scenes_batch(session, video_id, scenes_data)
            results["steps"]["scene_detection"] = f"success ({len(scenes_data)} scenes)"
        except Exception as e:
            logger.error(f"Scene detection failed: {e}\n{traceback.format_exc()}")
            results["steps"]["scene_detection"] = f"failed: {str(e)}"

        await _update_progress(video_id, 35, "Scene detection complete", progress_callback)

        # =====================================================================
        # Step 3: Audio Analysis (35-50%)
        # =====================================================================
        await _update_progress(video_id, 37, "Analyzing audio...", progress_callback)
        audio_segments: list[dict] = []
        try:
            from backend.services.audio_analysis import analyze_audio
            from backend.utils.ffmpeg import extract_audio

            audio_path = settings.temp_dir / f"audio_{video_id}.wav"
            settings.temp_dir.mkdir(parents=True, exist_ok=True)
            extract_audio(video_path, audio_path)
            audio_segments = analyze_audio(audio_path)
            results["steps"]["audio_analysis"] = f"success ({len(audio_segments)} segments)"

            # Clean up temp audio
            if audio_path.exists():
                audio_path.unlink()
        except Exception as e:
            logger.error(f"Audio analysis failed: {e}\n{traceback.format_exc()}")
            results["steps"]["audio_analysis"] = f"failed: {str(e)}"

        await _update_progress(video_id, 50, "Audio analysis complete", progress_callback)

        # =====================================================================
        # Step 4: Face Tracking (50-65%)
        # =====================================================================
        await _update_progress(video_id, 52, "Tracking faces...", progress_callback)
        face_data: list[dict] = []
        try:
            from backend.services.face_tracking import track_faces
            face_data = track_faces(
                video_path,
                sample_every_n=settings.face_sample_every_n_frames,
            )
            results["steps"]["face_tracking"] = f"success ({len(face_data)} frames)"
        except Exception as e:
            logger.error(f"Face tracking failed: {e}\n{traceback.format_exc()}")
            results["steps"]["face_tracking"] = f"failed: {str(e)}"

        await _update_progress(video_id, 65, "Face tracking complete", progress_callback)

        # =====================================================================
        # Step 5: Clip Scoring (65-70%)
        # =====================================================================
        await _update_progress(video_id, 67, "Scoring potential clips...", progress_callback)
        scored_clips: list[dict] = []
        try:
            from backend.services.clip_scoring import score_clips

            async with get_session_context() as session:
                video = await crud.get_video(session, video_id)
                video_duration = video.duration or 0

            weights = {
                "emotion": settings.scoring_weights.emotion,
                "dialogue": settings.scoring_weights.dialogue,
                "scene_change": settings.scoring_weights.scene_change,
                "audio": settings.scoring_weights.audio,
                "face": settings.scoring_weights.face,
            }
            scored_clips = score_clips(
                video_duration=video_duration,
                transcript=transcript_data,
                scenes=scenes_data,
                audio_segments=audio_segments,
                face_data=face_data,
                clip_durations=settings.clip_durations,
                weights=weights,
                max_clips=settings.max_clips_per_video,
                min_gap=float(settings.min_clip_gap_seconds),
            )
            results["steps"]["clip_scoring"] = f"success ({len(scored_clips)} clips selected)"
        except Exception as e:
            logger.error(f"Clip scoring failed: {e}\n{traceback.format_exc()}")
            results["steps"]["clip_scoring"] = f"failed: {str(e)}"

        await _update_progress(video_id, 70, "Clip scoring complete", progress_callback)

        if not scored_clips:
            logger.warning(f"No clips scored for video {video_id}. Skipping generation.")
            async with get_session_context() as session:
                await crud.update_video_status(
                    session, video_id,
                    status=VideoStatus.COMPLETED,
                    progress=100,
                    step="Completed (no clips generated)",
                )
            results["clips_generated"] = 0
            return results

        # =====================================================================
        # Step 6: Clip Generation (70-85%)
        # =====================================================================
        await _update_progress(video_id, 72, "Generating clips...", progress_callback)
        clip_records: list[Any] = []
        try:
            from backend.services.clip_generator import generate_clip

            settings.output_dir.mkdir(parents=True, exist_ok=True)
            total_clips = len(scored_clips)

            for i, clip_info in enumerate(scored_clips):
                clip_num = i + 1
                pct = 72 + int((i / total_clips) * 13)
                await _update_progress(
                    video_id, pct,
                    f"Generating clip {clip_num}/{total_clips}...",
                    progress_callback,
                )

                output_filename = f"clip_{video_id}_{clip_num:03d}.mp4"
                output_path = settings.output_dir / output_filename

                # Filter face data for this clip's time range
                clip_face_data = [
                    f for f in face_data
                    if clip_info["start"] <= f.get("time", 0) <= clip_info["end"]
                ]

                try:
                    generate_clip(
                        video_path=video_path,
                        output_path=output_path,
                        start_time=clip_info["start"],
                        end_time=clip_info["end"],
                        crop_data=clip_face_data if clip_face_data else None,
                    )

                    async with get_session_context() as session:
                        clip_record = await crud.create_clip(
                            session,
                            video_id=video_id,
                            clip_number=clip_num,
                            start_time=clip_info["start"],
                            end_time=clip_info["end"],
                            total_score=clip_info.get("total_score"),
                            score_breakdown=clip_info.get("breakdown"),
                        )
                        await crud.update_clip(
                            session, clip_record.id,
                            output_path=str(output_path),
                            status=ClipStatus.COMPLETED,
                            crop_data_json=clip_face_data,
                        )
                        clip_records.append({"id": clip_record.id, "path": str(output_path), "info": clip_info})
                except Exception as e:
                    logger.error(f"Failed to generate clip {clip_num}: {e}")

            results["steps"]["clip_generation"] = f"success ({len(clip_records)} clips)"
            results["clips_generated"] = len(clip_records)
        except Exception as e:
            logger.error(f"Clip generation failed: {e}\n{traceback.format_exc()}")
            results["steps"]["clip_generation"] = f"failed: {str(e)}"

        await _update_progress(video_id, 85, "Clip generation complete", progress_callback)

        # =====================================================================
        # Step 7: Subtitle Generation (85-90%)
        # =====================================================================
        await _update_progress(video_id, 86, "Generating subtitles...", progress_callback)
        try:
            from backend.services.subtitles import generate_srt, generate_vtt

            settings.subtitle_dir.mkdir(parents=True, exist_ok=True)
            segments = transcript_data.get("segments", [])

            for clip_rec in clip_records:
                clip_id = clip_rec["id"]
                clip_info = clip_rec["info"]

                # SRT
                srt_path = settings.subtitle_dir / f"clip_{video_id}_{clip_id}.srt"
                generate_srt(segments, srt_path, clip_start=clip_info["start"], clip_end=clip_info["end"])
                async with get_session_context() as session:
                    await crud.create_subtitle(session, clip_id, SubtitleFormat.SRT, str(srt_path))

                # VTT
                vtt_path = settings.subtitle_dir / f"clip_{video_id}_{clip_id}.vtt"
                generate_vtt(segments, vtt_path, clip_start=clip_info["start"], clip_end=clip_info["end"])
                async with get_session_context() as session:
                    await crud.create_subtitle(session, clip_id, SubtitleFormat.VTT, str(vtt_path))

            results["steps"]["subtitles"] = "success"
        except Exception as e:
            logger.error(f"Subtitle generation failed: {e}\n{traceback.format_exc()}")
            results["steps"]["subtitles"] = f"failed: {str(e)}"

        await _update_progress(video_id, 90, "Subtitles complete", progress_callback)

        # =====================================================================
        # Step 8: Metadata Generation (90-95%)
        # =====================================================================
        await _update_progress(video_id, 91, "Generating metadata...", progress_callback)
        try:
            from backend.services.metadata_generator import generate_metadata

            for clip_rec in clip_records:
                clip_id = clip_rec["id"]
                clip_info = clip_rec["info"]

                # Extract transcript text for this clip's time range
                clip_segments = [
                    s for s in transcript_data.get("segments", [])
                    if s.get("start", s.get("t0", 0)) >= clip_info["start"]
                    and s.get("end", s.get("t1", 0)) <= clip_info["end"]
                ]
                clip_text = " ".join(s.get("text", "") for s in clip_segments).strip()
                if not clip_text:
                    clip_text = transcript_data.get("full_text", "")[:500]

                metadata = generate_metadata(clip_text, model=settings.ollama_model)
                async with get_session_context() as session:
                    await crud.update_clip(
                        session, clip_id,
                        title=metadata.get("title", f"Clip {clip_rec['info'].get('start', 0):.0f}s"),
                        description=metadata.get("description", ""),
                        hashtags=metadata.get("hashtags", ""),
                        keywords=metadata.get("keywords", ""),
                    )

            results["steps"]["metadata"] = "success"
        except Exception as e:
            logger.error(f"Metadata generation failed: {e}\n{traceback.format_exc()}")
            results["steps"]["metadata"] = f"failed: {str(e)}"

        await _update_progress(video_id, 95, "Metadata complete", progress_callback)

        # =====================================================================
        # Step 9: Thumbnail Generation (95-100%)
        # =====================================================================
        await _update_progress(video_id, 96, "Generating thumbnails...", progress_callback)
        try:
            from backend.services.thumbnail_generator import generate_thumbnails

            settings.thumbnail_dir.mkdir(parents=True, exist_ok=True)

            for clip_rec in clip_records:
                clip_id = clip_rec["id"]
                clip_info = clip_rec["info"]
                clip_thumb_dir = settings.thumbnail_dir / f"clip_{clip_id}"
                clip_thumb_dir.mkdir(parents=True, exist_ok=True)

                thumbs = generate_thumbnails(
                    video_path=video_path,
                    output_dir=clip_thumb_dir,
                    clip_start=clip_info["start"],
                    clip_end=clip_info["end"],
                )

                async with get_session_context() as session:
                    for thumb in thumbs:
                        await crud.create_thumbnail(
                            session, clip_id,
                            filepath=thumb["path"],
                            score=thumb.get("score"),
                            format=thumb.get("format", "jpg"),
                            is_selected=thumb.get("is_selected", False),
                        )

            results["steps"]["thumbnails"] = "success"
        except Exception as e:
            logger.error(f"Thumbnail generation failed: {e}\n{traceback.format_exc()}")
            results["steps"]["thumbnails"] = f"failed: {str(e)}"

        # =====================================================================
        # Complete
        # =====================================================================
        await _update_progress(video_id, 100, "Processing complete", progress_callback)
        async with get_session_context() as session:
            await crud.update_video_status(
                session, video_id,
                status=VideoStatus.COMPLETED,
                progress=100,
                step="Completed",
            )

        logger.info(
            f"Pipeline complete for video {video_id}: "
            f"{results['clips_generated']} clips generated, "
            f"steps: {results['steps']}"
        )
        return results

    except Exception as e:
        logger.error(f"Pipeline failed for video {video_id}: {e}\n{traceback.format_exc()}")
        async with get_session_context() as session:
            await crud.update_video_status(
                session, video_id,
                status=VideoStatus.FAILED,
                progress=-1,
                step="Pipeline failed",
                error=str(e),
            )
        raise
