"""Shared test fixtures: test database, mock APIs, test client."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Set test environment before any app imports
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://agent:test@localhost:5432/content_agent_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-secret")
os.environ.setdefault("SLACK_APP_TOKEN", "xapp-test")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def app():
    """Create a FastAPI test app."""
    from agent.main import app as fastapi_app
    yield fastapi_app


@pytest.fixture
async def client(app):
    """Async HTTP test client for FastAPI."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_claude():
    """Mock Anthropic Claude API responses."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(type="text", text="Generated post content here.")]
    mock_message.usage = MagicMock(input_tokens=100, output_tokens=50)

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    with patch("openai.AsyncOpenAI", return_value=mock_client) as mock_cls:
        mock_cls.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.aclose = AsyncMock()
    return mock


@pytest.fixture
def sample_signal_data():
    """Sample content signal data for tests."""
    return {
        "source": "rss",
        "source_url": "https://example.com/article/test-ai-development",
        "title": "New Advances in AI Agent Development",
        "summary": "Researchers have developed a new framework for building AI agents that can autonomously handle complex tasks.",
        "raw_data": {
            "feed_name": "TechCrunch AI",
            "published": "2026-03-24T10:00:00Z",
        },
    }


@pytest.fixture
def sample_content_brief():
    """Sample content brief for tests."""
    return {
        "signal_id": "00000000-0000-0000-0000-000000000001",
        "topic": "AI Agent Development Frameworks",
        "angle": "Why workflow integration matters more than model accuracy for AI agents",
        "key_points": [
            "New framework reduces agent development time by 60%",
            "Focus on task decomposition over raw model performance",
            "Integration with existing developer tools is key",
        ],
        "target_platforms": ["linkedin", "twitter"],
        "priority": "high",
    }
