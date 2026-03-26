"""Celery tasks for research crawling and daily briefing."""

from __future__ import annotations

from agent.tasks.celery_app import celery_app


@celery_app.task(name="agent.tasks.research.run_research_crawl")
def run_research_crawl() -> dict:
    """Periodic task: crawl all configured sources for new signals.

    Implemented in Phase 3 (Research Engine).
    """
    # TODO: Implement in Phase 3
    return {"status": "not_implemented", "message": "Research crawl will be implemented in Phase 3"}


@celery_app.task(name="agent.tasks.research.send_daily_briefing")
def send_daily_briefing() -> dict:
    """Daily morning task: send a summary of pending content and yesterday's performance.

    Implemented in Phase 7 (Slack Bot).
    """
    # TODO: Implement in Phase 7
    return {"status": "not_implemented", "message": "Daily briefing will be implemented in Phase 7"}
