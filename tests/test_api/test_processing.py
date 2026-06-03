"""
Tests for processing API endpoints.
"""

import io
from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_process_video_not_found(client: AsyncClient):
    """Test starting processing for a non-existent video."""
    response = await client.post("/api/process/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_status_not_found(client: AsyncClient):
    """Test getting status for a non-existent video."""
    response = await client.get("/api/status/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_process_video(client: AsyncClient, mock_ffprobe):
    """Test starting video processing."""
    # Upload first
    content = b"\x00\x00\x00\x1c" + b"ftyp" + b"isom" + b"\x00\x00\x02\x00" + b"isomiso2mp41" + b"\x00" * 1024
    upload_resp = await client.post("/api/upload", files={"file": ("test.mp4", io.BytesIO(content), "video/mp4")})
    video_id = upload_resp.json()["id"]

    # Start processing
    response = await client.post(f"/api/process/{video_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"


@pytest.mark.asyncio
async def test_get_processing_status(client: AsyncClient, mock_ffprobe):
    """Test getting processing status after starting."""
    content = b"\x00\x00\x00\x1c" + b"ftyp" + b"isom" + b"\x00\x00\x02\x00" + b"isomiso2mp41" + b"\x00" * 1024
    upload_resp = await client.post("/api/upload", files={"file": ("test.mp4", io.BytesIO(content), "video/mp4")})
    video_id = upload_resp.json()["id"]

    await client.post(f"/api/process/{video_id}")

    response = await client.get(f"/api/status/{video_id}")
    assert response.status_code == 200
    data = response.json()
    assert "progress" in data
    assert "status" in data


@pytest.mark.asyncio
async def test_analytics(client: AsyncClient):
    """Test analytics endpoint."""
    response = await client.get("/api/analytics")
    assert response.status_code == 200
    data = response.json()
    assert "total_videos" in data
    assert "total_clips" in data
