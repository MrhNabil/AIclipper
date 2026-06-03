"""
Tests for clip API endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_clips_empty(client: AsyncClient):
    """Test listing clips when none exist."""
    response = await client.get("/api/clips")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["clips"] == []


@pytest.mark.asyncio
async def test_get_clip_not_found(client: AsyncClient):
    """Test getting a non-existent clip."""
    response = await client.get("/api/clips/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_clip_not_found(client: AsyncClient):
    """Test deleting a non-existent clip."""
    response = await client.delete("/api/clips/99999")
    assert response.status_code == 404
