"""
AIClipper Test Fixtures

Shared pytest fixtures for API tests, database tests, and service tests.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set test environment before importing app modules
os.environ["APP_ENV"] = "test"
os.environ["APP_DEBUG"] = "false"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    from backend.database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    factory = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client with mocked database."""
    from backend.database.models import Base

    # Create test session factory
    factory = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _test_get_session():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    from backend.api.app import app
    from backend.database.engine import get_session

    app.dependency_overrides[get_session] = _test_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sample_video_path(tmp_path) -> Path:
    """Create a minimal test video file (just bytes, not a real video)."""
    video_file = tmp_path / "test_video.mp4"
    # Write a minimal ftyp box to make it look like an MP4
    with open(video_file, "wb") as f:
        # ftyp box header
        f.write(b"\x00\x00\x00\x1c")  # box size (28 bytes)
        f.write(b"ftyp")              # box type
        f.write(b"isom")              # major brand
        f.write(b"\x00\x00\x02\x00")  # minor version
        f.write(b"isomiso2mp41")       # compatible brands
        f.write(b"\x00" * 1024)       # padding to make it non-trivial size
    return video_file


@pytest.fixture
def mock_settings():
    """Mock settings with test defaults."""
    from backend.utils.config import Settings
    return Settings(
        app_env="test",
        app_debug=False,
        database_url="sqlite+aiosqlite://",
        upload_dir=Path(tempfile.mkdtemp()),
        output_dir=Path(tempfile.mkdtemp()),
        subtitle_dir=Path(tempfile.mkdtemp()),
        thumbnail_dir=Path(tempfile.mkdtemp()),
        log_dir=Path(tempfile.mkdtemp()),
        model_dir=Path(tempfile.mkdtemp()),
        temp_dir=Path(tempfile.mkdtemp()),
        data_dir=Path(tempfile.mkdtemp()),
    )


@pytest.fixture
def mock_ffprobe():
    """Mock FFprobe to avoid needing FFmpeg in tests."""
    mock_result = {
        "duration": 120.5,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "codec": "h264",
        "audio_codec": "aac",
        "bitrate": 5000000,
        "filesize": 75000000,
        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
    }
    with patch("backend.utils.validators.probe_video", return_value=mock_result) as mock:
        yield mock


@pytest.fixture
def sample_transcript():
    """Sample transcript data for testing services."""
    return {
        "language": "en",
        "full_text": "Hello everyone welcome to this amazing video. Today we'll discuss something incredible. Let's get started!",
        "segments": [
            {"start": 0.0, "end": 3.5, "text": "Hello everyone welcome to this amazing video."},
            {"start": 3.5, "end": 7.0, "text": "Today we'll discuss something incredible."},
            {"start": 7.0, "end": 10.0, "text": "Let's get started!"},
        ],
        "words": [
            {"word": "Hello", "start": 0.0, "end": 0.5},
            {"word": "everyone", "start": 0.6, "end": 1.2},
            {"word": "welcome", "start": 1.3, "end": 1.8},
            {"word": "to", "start": 1.9, "end": 2.0},
            {"word": "this", "start": 2.1, "end": 2.3},
            {"word": "amazing", "start": 2.4, "end": 2.8},
            {"word": "video.", "start": 2.9, "end": 3.4},
        ],
    }


@pytest.fixture
def sample_scenes():
    """Sample scene detection data."""
    return [
        {"start": 0.0, "end": 15.0, "duration": 15.0, "score": 0.8},
        {"start": 15.0, "end": 45.0, "duration": 30.0, "score": 0.6},
        {"start": 45.0, "end": 90.0, "duration": 45.0, "score": 0.7},
        {"start": 90.0, "end": 120.0, "duration": 30.0, "score": 0.5},
    ]


@pytest.fixture
def sample_audio_segments():
    """Sample audio analysis data."""
    return [
        {"start": 0.0, "end": 5.0, "energy_score": 0.3, "laughter_detected": False, "crowd_reaction": False, "emotion_intensity": 0.4},
        {"start": 5.0, "end": 10.0, "energy_score": 0.8, "laughter_detected": True, "crowd_reaction": False, "emotion_intensity": 0.9},
        {"start": 10.0, "end": 15.0, "energy_score": 0.6, "laughter_detected": False, "crowd_reaction": True, "emotion_intensity": 0.7},
    ]


@pytest.fixture
def sample_face_data():
    """Sample face tracking data."""
    return [
        {"time": 0.0, "crop_x": 420, "crop_y": 0, "crop_w": 1080, "crop_h": 1920, "face_visible": True, "num_faces": 1},
        {"time": 1.0, "crop_x": 425, "crop_y": 0, "crop_w": 1080, "crop_h": 1920, "face_visible": True, "num_faces": 1},
        {"time": 2.0, "crop_x": 430, "crop_y": 0, "crop_w": 1080, "crop_h": 1920, "face_visible": False, "num_faces": 0},
    ]
