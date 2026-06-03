"""
AIClipper Configuration Module

Loads configuration from .env files and YAML config, providing typed access
to all application settings via Pydantic Settings.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Resolve project root – two levels up from this file (backend/utils/config.py)
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent.parent


def _load_yaml_config(path: Path | None = None) -> dict[str, Any]:
    """Load the YAML configuration file and return as a flat dict."""
    if path is None:
        path = PROJECT_ROOT / "configs" / "default.yaml"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data


# ---------------------------------------------------------------------------
# Sub-models for nested configuration
# ---------------------------------------------------------------------------

class ScoringWeights(BaseSettings):
    """Clip scoring weight configuration."""
    emotion: float = 0.25
    dialogue: float = 0.20
    scene_change: float = 0.20
    audio: float = 0.20
    face: float = 0.15

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> "ScoringWeights":
        total = self.emotion + self.dialogue + self.scene_change + self.audio + self.face
        if abs(total - 1.0) > 0.01:
            # Normalize automatically
            self.emotion /= total
            self.dialogue /= total
            self.scene_change /= total
            self.audio /= total
            self.face /= total
        return self


class SubtitleFont(BaseSettings):
    """Subtitle font settings."""
    family: str = "Arial"
    size: int = 24
    color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline_width: int = 2
    shadow_color: str = "#33000000"
    shadow_offset: int = 2


class SubtitleHighlight(BaseSettings):
    """Active word highlight settings."""
    enabled: bool = True
    color: str = "#FFD700"
    style: str = "color"  # color, background, underline


class SubtitleStyle(BaseSettings):
    """Complete subtitle style configuration."""
    default_format: str = "burned"  # srt, vtt, burned
    font: SubtitleFont = SubtitleFont()
    highlight: SubtitleHighlight = SubtitleHighlight()
    position: str = "bottom"  # top, center, bottom
    max_chars_per_line: int = 42
    max_lines: int = 2


class OutputSettings(BaseSettings):
    """Video output settings."""
    width: int = 1080
    height: int = 1920
    fps: int = 30
    codec: str = "libx264"
    crf: int = 21
    preset: str = "medium"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    format: str = "mp4"


# ---------------------------------------------------------------------------
# Main Settings
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """
    Main application settings.

    Loads from (in priority order):
    1. Environment variables
    2. .env file
    3. YAML config file (configs/default.yaml)
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "AIClipper"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    secret_key: str = "change-this-to-a-random-secret-key"

    # --- Paths ---
    upload_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "uploads")
    output_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "outputs")
    subtitle_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "subtitles")
    thumbnail_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "thumbnails")
    log_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "logs")
    model_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "models")
    temp_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "temp")
    data_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "data")

    # --- Database ---
    database_url: str = Field(
        default_factory=lambda: f"sqlite+aiosqlite:///{PROJECT_ROOT / 'data' / 'aiclipper.db'}"
    )

    # --- Whisper ---
    whisper_model: str = "small.en"
    whisper_model_path: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "models" / "ggml-small.en.bin"
    )
    whisper_threads: int = 4
    whisper_language: str = "auto"

    # --- Ollama ---
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2"
    ollama_timeout: int = 120

    # --- MediaPipe ---
    mediapipe_model_path: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "models" / "blaze_face_short_range.tflite"
    )
    face_sample_every_n_frames: int = 3

    # --- FFmpeg ---
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    # --- Clip Settings ---
    clip_durations: list[int] = [15, 30, 60]
    max_clips_per_video: int = 10
    min_clip_gap_seconds: int = 10

    # --- Scoring Weights ---
    scoring_weights: ScoringWeights = ScoringWeights()

    # --- Subtitle Style ---
    subtitle_style: SubtitleStyle = SubtitleStyle()

    # --- Output ---
    output_settings: OutputSettings = OutputSettings()

    # --- Processing Limits ---
    max_video_duration_seconds: int = 14400  # 4 hours
    supported_formats: list[str] = ["mp4", "mkv", "avi", "mov"]
    max_file_size_mb: int = 4096

    # --- YouTube ---
    youtube_client_secrets_file: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "configs" / "client_secret_youtube.json"
    )
    youtube_token_file: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "data" / "youtube_token.json"
    )

    # --- Facebook ---
    facebook_app_id: str = ""
    facebook_app_secret: str = ""
    facebook_page_id: str = ""
    facebook_access_token: str = ""

    @field_validator("clip_durations", mode="before")
    @classmethod
    def _parse_clip_durations(cls, v: Any) -> list[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",")]
        return v

    @field_validator("supported_formats", mode="before")
    @classmethod
    def _parse_formats(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [x.strip().lower() for x in v.split(",")]
        return v

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        for d in [
            self.upload_dir,
            self.output_dir,
            self.subtitle_dir,
            self.thumbnail_dir,
            self.log_dir,
            self.model_dir,
            self.temp_dir,
            self.data_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_yaml(cls, yaml_path: Path | None = None, **overrides: Any) -> "Settings":
        """Create Settings with YAML defaults, then layer .env and env vars on top."""
        yaml_data = _load_yaml_config(yaml_path)
        # Flatten nested YAML keys into env-style names
        flat: dict[str, Any] = {}
        if "whisper" in yaml_data:
            w = yaml_data["whisper"]
            flat["whisper_model"] = w.get("model", "small.en")
            flat["whisper_threads"] = w.get("threads", 4)
            flat["whisper_language"] = w.get("language", "auto")
        if "ollama" in yaml_data:
            o = yaml_data["ollama"]
            flat["ollama_host"] = o.get("host", "http://localhost:11434")
            flat["ollama_model"] = o.get("model", "qwen2")
            flat["ollama_timeout"] = o.get("timeout", 120)
        if "clips" in yaml_data:
            c = yaml_data["clips"]
            flat["clip_durations"] = c.get("durations", [15, 30, 60])
            flat["max_clips_per_video"] = c.get("max_per_video", 10)
            flat["min_clip_gap_seconds"] = c.get("min_gap_seconds", 10)
        if "output" in yaml_data:
            o = yaml_data["output"]
            if "resolution" in o:
                flat.setdefault("output_settings", OutputSettings())
        flat.update(overrides)
        return cls(**flat)


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    settings = Settings()
    settings.ensure_directories()
    return settings
