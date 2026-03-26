"""Test the /health endpoint and root endpoint."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Test that the root endpoint returns app info."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Content Creator AI Agent"
    assert "version" in data
    assert data["docs"] == "/docs"


@pytest.mark.asyncio
async def test_health_endpoint_degraded(client):
    """Test health endpoint when services are unavailable (test environment)."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "environment" in data
    assert "database" in data
    assert "redis" in data
