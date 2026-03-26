"""Pydantic BaseSettings — loads .env + YAML config files."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Resolve config directory: supports both local dev and Docker
# ---------------------------------------------------------------------------
def _find_config_dir() -> Path:
    """Find config/ directory relative to project root."""
    # Docker mount: /app/config
    docker_path = Path("/app/config")
    if docker_path.exists():
        return docker_path

    # Local dev: walk up from this file to find config/
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "config"
        if candidate.is_dir() and (candidate / "brand_voice.yaml").exists():
            return candidate

    raise FileNotFoundError("Could not locate config/ directory with YAML files")


def _load_yaml(filename: str) -> dict[str, Any]:
    """Load a YAML config file from the config directory."""
    config_dir = _find_config_dir()
    filepath = config_dir / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# Main Settings class
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database ---
    database_url: str = "postgresql+asyncpg://agent:changeme@localhost:5432/content_agent"
    db_password: str = "changeme"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- OpenAI ---
    openai_api_key: str = ""
    default_model: str = "gpt-4o"
    premium_model: str = "gpt-4o"

    # --- Slack (Socket Mode) ---
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_app_token: str = ""
    slack_channel_id: str = ""

    # --- LinkedIn OAuth 2.0 ---
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_access_token: str = ""
    linkedin_refresh_token: str = ""
    linkedin_person_urn: str = ""

    # --- Twitter / X ---
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_token_secret: str = ""
    twitter_bearer_token: str = ""

    # --- Reddit ---
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "content-creator-agent/1.0"

    # --- Embeddings ---
    voyage_api_key: str = ""

    # --- Scheduling ---
    research_interval_hours: int = 4
    analytics_delay_hours: int = 24
    user_timezone: str = "Asia/Kolkata"

    # --- App ---
    log_level: str = "INFO"
    environment: str = "development"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def sync_database_url(self) -> str:
        """Return a synchronous database URL (for Alembic)."""
        return self.database_url.replace("+asyncpg", "+psycopg2").replace("+aiosqlite", "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton for settings."""
    return Settings()


@lru_cache(maxsize=1)
def get_brand_config() -> dict[str, Any]:
    """Load brand voice configuration."""
    return _load_yaml("brand_voice.yaml")


@lru_cache(maxsize=1)
def get_platforms_config() -> dict[str, Any]:
    """Load platform configuration."""
    return _load_yaml("platforms.yaml")


@lru_cache(maxsize=1)
def get_sources_config() -> dict[str, Any]:
    """Load research sources configuration."""
    return _load_yaml("sources.yaml")
