"""Celery tasks for scheduled content publishing."""

from __future__ import annotations

from agent.tasks.celery_app import celery_app


@celery_app.task(name="agent.tasks.publish.publish_due_content")
def publish_due_content() -> dict:
    """Periodic task: check for approved content that is due to be published.

    Runs every 5 minutes via Celery Beat.
    Implemented in Phase 8 (Publishers).
    """
    # TODO: Implement in Phase 8
    return {"status": "not_implemented", "message": "Publish task will be implemented in Phase 8"}
