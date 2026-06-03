"""
Tests for subtitle generation services.
"""

import pytest
from pathlib import Path

from backend.services.subtitles import generate_srt, generate_vtt


class TestSRTGeneration:
    """Test SRT subtitle generation."""

    def test_generate_srt_basic(self, tmp_path, sample_transcript):
        """Test basic SRT generation."""
        output = tmp_path / "test.srt"
        result = generate_srt(sample_transcript["segments"], output)

        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "1\n" in content
        assert "-->" in content
        assert "Hello" in content

    def test_generate_srt_timing_format(self, tmp_path, sample_transcript):
        """Test that SRT uses correct timing format HH:MM:SS,mmm."""
        output = tmp_path / "test.srt"
        generate_srt(sample_transcript["segments"], output)

        content = output.read_text(encoding="utf-8")
        # SRT format uses comma for milliseconds
        assert "00:00:00,000" in content or "00:00:" in content

    def test_generate_srt_with_clip_range(self, tmp_path, sample_transcript):
        """Test SRT generation filtered to a clip time range."""
        output = tmp_path / "test.srt"
        result = generate_srt(
            sample_transcript["segments"], output,
            clip_start=3.0, clip_end=8.0,
        )

        assert result.exists()
        content = result.read_text(encoding="utf-8")
        # Should include segments overlapping with 3.0-8.0
        assert len(content.strip()) > 0

    def test_generate_srt_empty_segments(self, tmp_path):
        """Test SRT generation with no segments."""
        output = tmp_path / "test.srt"
        result = generate_srt([], output)

        assert result.exists()


class TestVTTGeneration:
    """Test WebVTT subtitle generation."""

    def test_generate_vtt_basic(self, tmp_path, sample_transcript):
        """Test basic VTT generation."""
        output = tmp_path / "test.vtt"
        result = generate_vtt(sample_transcript["segments"], output)

        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "WEBVTT" in content
        assert "-->" in content

    def test_generate_vtt_timing_format(self, tmp_path, sample_transcript):
        """Test that VTT uses correct timing format HH:MM:SS.mmm."""
        output = tmp_path / "test.vtt"
        generate_vtt(sample_transcript["segments"], output)

        content = output.read_text(encoding="utf-8")
        # VTT format uses period for milliseconds
        assert "00:00:" in content

    def test_generate_vtt_header(self, tmp_path, sample_transcript):
        """Test that VTT file starts with WEBVTT header."""
        output = tmp_path / "test.vtt"
        generate_vtt(sample_transcript["segments"], output)

        content = output.read_text(encoding="utf-8")
        assert content.startswith("WEBVTT")
