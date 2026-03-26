# Content Creator AI Agent

AI-powered content creation agent for LinkedIn and X/Twitter.

## Quick Start

```bash
# Install dependencies
uv venv .venv && uv pip install -e ".[dev]"

# Copy environment file
cp .env.example .env
# Edit .env with your API keys

# Run locally
uvicorn agent.main:app --reload

# Run with Docker
docker compose up
```

## Architecture

See the PRD for full details. This is a Phase 1 MVP.
