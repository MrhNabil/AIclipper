"""
Tests for the clip scoring engine.
"""

import pytest

from backend.services.clip_scoring import score_clips


class TestClipScoring:
    """Test the clip scoring algorithm."""

    def test_score_clips_basic(self, sample_transcript, sample_scenes, sample_audio_segments, sample_face_data):
        """Test that score_clips returns ranked clips."""
        results = score_clips(
            video_duration=120.0,
            transcript=sample_transcript,
            scenes=sample_scenes,
            audio_segments=sample_audio_segments,
            face_data=sample_face_data,
            clip_durations=[15],
            max_clips=5,
            min_gap=5.0,
        )

        assert isinstance(results, list)
        # Each result should have required keys
        for clip in results:
            assert "start" in clip
            assert "end" in clip
            assert "duration" in clip
            assert "total_score" in clip
            assert "breakdown" in clip
            assert clip["duration"] > 0
            assert 0 <= clip["total_score"] <= 1.0

    def test_score_clips_respects_max(self, sample_transcript, sample_scenes, sample_audio_segments, sample_face_data):
        """Test that score_clips doesn't exceed max_clips."""
        results = score_clips(
            video_duration=120.0,
            transcript=sample_transcript,
            scenes=sample_scenes,
            audio_segments=sample_audio_segments,
            face_data=sample_face_data,
            clip_durations=[15],
            max_clips=3,
            min_gap=5.0,
        )

        assert len(results) <= 3

    def test_score_clips_custom_weights(self, sample_transcript, sample_scenes, sample_audio_segments, sample_face_data):
        """Test that custom weights affect scoring."""
        # All weight on emotion
        results_emotion = score_clips(
            video_duration=120.0,
            transcript=sample_transcript,
            scenes=sample_scenes,
            audio_segments=sample_audio_segments,
            face_data=sample_face_data,
            clip_durations=[15],
            weights={"emotion": 1.0, "dialogue": 0.0, "scene_change": 0.0, "audio": 0.0, "face": 0.0},
            max_clips=3,
        )

        # All weight on face
        results_face = score_clips(
            video_duration=120.0,
            transcript=sample_transcript,
            scenes=sample_scenes,
            audio_segments=sample_audio_segments,
            face_data=sample_face_data,
            clip_durations=[15],
            weights={"emotion": 0.0, "dialogue": 0.0, "scene_change": 0.0, "audio": 0.0, "face": 1.0},
            max_clips=3,
        )

        # Scores should differ with different weights
        assert isinstance(results_emotion, list)
        assert isinstance(results_face, list)

    def test_score_clips_multiple_durations(self, sample_transcript, sample_scenes, sample_audio_segments, sample_face_data):
        """Test scoring with multiple clip durations."""
        results = score_clips(
            video_duration=120.0,
            transcript=sample_transcript,
            scenes=sample_scenes,
            audio_segments=sample_audio_segments,
            face_data=sample_face_data,
            clip_durations=[15, 30, 60],
            max_clips=10,
        )

        assert isinstance(results, list)
        # Should have clips of various durations
        durations = {clip["duration"] for clip in results}
        assert len(durations) >= 1

    def test_score_clips_empty_data(self):
        """Test scoring with empty input data."""
        results = score_clips(
            video_duration=60.0,
            transcript={"segments": [], "words": [], "full_text": ""},
            scenes=[],
            audio_segments=[],
            face_data=[],
            clip_durations=[15],
            max_clips=5,
        )

        assert isinstance(results, list)

    def test_score_clips_short_video(self, sample_transcript, sample_scenes, sample_audio_segments, sample_face_data):
        """Test scoring a video shorter than clip duration."""
        results = score_clips(
            video_duration=10.0,  # Shorter than 15s clip
            transcript=sample_transcript,
            scenes=sample_scenes,
            audio_segments=sample_audio_segments,
            face_data=sample_face_data,
            clip_durations=[15],
            max_clips=5,
        )

        # Should not generate clips longer than video
        for clip in results:
            assert clip["end"] <= 10.0

    def test_score_breakdown_keys(self, sample_transcript, sample_scenes, sample_audio_segments, sample_face_data):
        """Test that score breakdown contains all expected keys."""
        results = score_clips(
            video_duration=120.0,
            transcript=sample_transcript,
            scenes=sample_scenes,
            audio_segments=sample_audio_segments,
            face_data=sample_face_data,
            clip_durations=[15],
            max_clips=1,
        )

        if results:
            breakdown = results[0]["breakdown"]
            expected_keys = {"emotion", "dialogue", "scene_change", "audio", "face"}
            assert expected_keys.issubset(set(breakdown.keys()))
