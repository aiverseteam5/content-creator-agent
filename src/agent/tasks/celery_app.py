"""Celery configuration and beat schedule."""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

# ---------------------------------------------------------------------------
# Celery App
# ---------------------------------------------------------------------------
celery_app = Celery(
    "content_agent",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone=os.environ.get("USER_TIMEZONE", "Asia/Kolkata"),
    enable_utc=True,

    # Task routing
    task_routes={
        "agent.tasks.research.*": {"queue": "research"},
        "agent.tasks.publish.*": {"queue": "publish"},
        "agent.tasks.analytics.*": {"queue": "analytics"},
    },

    # Default queue for unmatched tasks
    task_default_queue="default",

    # Result expiry (24 hours)
    result_expires=86400,

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)

# ---------------------------------------------------------------------------
# Beat Schedule (periodic tasks)
# ---------------------------------------------------------------------------
celery_app.conf.beat_schedule = {
    # Research crawl every 4 hours
    "research-crawl": {
        "task": "agent.tasks.research.run_research_crawl",
        "schedule": crontab(
            minute=0,
            hour=f"*/{os.environ.get('RESEARCH_INTERVAL_HOURS', '4')}",
        ),
    },
    # Check for scheduled posts every 5 minutes
    "publish-scheduled": {
        "task": "agent.tasks.publish.publish_due_content",
        "schedule": crontab(minute="*/5"),
    },
    # Daily morning briefing via Slack at 8:00 AM IST (2:30 AM UTC)
    "daily-briefing": {
        "task": "agent.tasks.research.send_daily_briefing",
        "schedule": crontab(minute=30, hour=2),  # 2:30 UTC = 8:00 IST
    },
}

# ---------------------------------------------------------------------------
# Auto-discover tasks
# ---------------------------------------------------------------------------
celery_app.autodiscover_tasks(["agent.tasks"])
