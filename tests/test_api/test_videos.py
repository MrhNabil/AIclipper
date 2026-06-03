"""
Tests for video API endpoints.
"""

import io
from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test the health check endpoint."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.asyncio
async def test_upload_video(client: AsyncClient, mock_ffprobe):
    """Test video upload endpoint."""
    # Create a fake MP4 file
    content = b"\x00\x00\x00\x1c" + b"ftyp" + b"isom" + b"\x00\x00\x02\x00" + b"isomiso2mp41" + b"\x00" * 1024

    response = await client.post(
        "/api/upload",
        files={"file": ("test.mp4", io.BytesIO(content), "video/mp4")},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "test.mp4"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_upload_invalid_format(client: AsyncClient):
    """Test that uploading an invalid format returns 400."""
    content = b"not a video file"

    response = await client.post(
        "/api/upload",
        files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_videos_empty(client: AsyncClient):
    """Test listing videos when none exist."""
    response = await client.get("/api/videos")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["videos"] == []


@pytest.mark.asyncio
async def test_list_videos_pagination(client: AsyncClient, mock_ffprobe):
    """Test video listing with pagination."""
    # Upload a video first
    content = b"\x00\x00\x00\x1c" + b"ftyp" + b"isom" + b"\x00\x00\x02\x00" + b"isomiso2mp41" + b"\x00" * 1024
    await client.post("/api/upload", files={"file": ("test.mp4", io.BytesIO(content), "video/mp4")})

    response = await client.get("/api/videos?offset=0&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_video_not_found(client: AsyncClient):
    """Test getting a non-existent video."""
    response = await client.get("/api/videos/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_video_detail(client: AsyncClient, mock_ffprobe):
    """Test getting video details."""
    content = b"\x00\x00\x00\x1c" + b"ftyp" + b"isom" + b"\x00\x00\x02\x00" + b"isomiso2mp41" + b"\x00" * 1024
    upload_resp = await client.post("/api/upload", files={"file": ("test.mp4", io.BytesIO(content), "video/mp4")})
    video_id = upload_resp.json()["id"]

    response = await client.get(f"/api/videos/{video_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == video_id
    assert data["filename"] == "test.mp4"
