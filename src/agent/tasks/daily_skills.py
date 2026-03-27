"""Celery tasks for the daily autonomous skill schedule (F15)."""

from __future__ import annotations

import os
from datetime import date
from typing import Any

import redis as redis_lib

from agent.core.config import get_settings
from agent.core.logging import get_logger
from agent.tasks.celery_app import celery_app

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_BUDGET_KEY_PREFIX = "daily_skill_spend_usd"
_STOP_FLAG_KEY = "agent_emergency_stop"

# Approximate cost per 1K tokens for gpt-4o (input + output blended)
_COST_PER_1K_TOKENS_USD = 0.010


def _redis() -> redis_lib.Redis:
    return redis_lib.from_url(_REDIS_URL, decode_responses=True)


def _budget_key() -> str:
    """Daily budget key resets automatically by date."""
    return f"{_BUDGET_KEY_PREFIX}:{date.today().isoformat()}"


def _is_stopped() -> bool:
    try:
        r = _redis()
        return bool(r.get(_STOP_FLAG_KEY))
    except Exception:
        return False


def _get_spend_usd() -> float:
    try:
        r = _redis()
        val = r.get(_budget_key())
        return float(str(val)) if val else 0.0
    except Exception:
        return 0.0


def _record_spend(usd: float) -> float:
    """Add `usd` to today's tally and return the new total."""
    try:
        r = _redis()
        key = _budget_key()
        pipe = r.pipeline()
        pipe.incrbyfloat(key, usd)
        pipe.expire(key, 86400 * 2)  # keep for 2 days
        results = pipe.execute()
        return float(results[0])
    except Exception:
        return 0.0


def _post_to_slack(message: str) -> None:
    """Fire-and-forget Slack message via slack_sdk WebClient."""
    try:
        from slack_sdk import WebClient

        from agent.core.config import get_settings

        settings = get_settings()
        if not settings.slack_bot_token or not settings.slack_channel_id:
            logger.warning("slack_notify_skipped", reason="token or channel not configured")
            return
        client = WebClient(token=settings.slack_bot_token)
        client.chat_postMessage(channel=settings.slack_channel_id, text=message)
    except Exception as exc:
        logger.error("slack_notify_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Generic scheduled skill runner
# ---------------------------------------------------------------------------
@celery_app.task(
    name="agent.tasks.daily_skills.run_scheduled_skill",
    bind=True,
    max_retries=2,
    default_retry_delay=300,  # 5 min back-off
)
def run_scheduled_skill(self: Any, skill_name: str, context: dict | None = None) -> dict:
    """
    Execute a named skill as part of the daily schedule.

    Guards:
    - Emergency stop flag in Redis
    - Daily API budget cap
    - Idempotency: skips if already ran today (Redis key)
    """
    context = context or {}

    # 1. Emergency stop
    if _is_stopped():
        logger.warning("scheduled_skill_stopped", skill=skill_name)
        return {"status": "stopped", "skill": skill_name}

    # 2. Idempotency — skip if already ran today
    idem_key = f"skill_ran:{skill_name}:{date.today().isoformat()}"
    try:
        r = _redis()
        already_ran = r.set(idem_key, "1", ex=86400, nx=True)
        if not already_ran:
            logger.info("scheduled_skill_skipped_idempotent", skill=skill_name)
            return {"status": "skipped_idempotent", "skill": skill_name}
    except Exception as exc:
        logger.warning("redis_idempotency_check_failed", error=str(exc))

    # 3. Budget guard
    settings = get_settings()
    budget = getattr(settings, "daily_api_budget_usd", 2.00)
    current_spend = _get_spend_usd()
    if current_spend >= budget:
        msg = (
            f":warning: *Daily budget cap hit* (${current_spend:.2f} / ${budget:.2f}). "
            f"Skipping `{skill_name}` skill run."
        )
        logger.warning("budget_cap_hit", skill=skill_name, spend=current_spend, budget=budget)
        _post_to_slack(msg)
        return {"status": "budget_cap", "skill": skill_name, "spend_usd": current_spend}

    # 4. Execute skill
    logger.info("scheduled_skill_starting", skill=skill_name, context_keys=list(context.keys()))
    from agent.skills.registry import execute_skill

    try:
        result = execute_skill(skill_name, context)
    except Exception as exc:
        logger.error("scheduled_skill_error", skill=skill_name, error=str(exc))
        raise self.retry(exc=exc) from exc

    # 5. Estimate cost and record spend (rough: 2K tokens per run)
    estimated_usd = 2.0 * _COST_PER_1K_TOKENS_USD
    new_total = _record_spend(estimated_usd)
    logger.info(
        "scheduled_skill_complete",
        skill=skill_name,
        success=result.success,
        spend_usd=estimated_usd,
        daily_total_usd=new_total,
    )

    # 6. Post result to Slack
    _post_to_slack(result.message)

    return {
        "status": "ok" if result.success else "failed",
        "skill": skill_name,
        "message": result.message,
        "spend_usd": estimated_usd,
        "daily_total_usd": new_total,
    }


# ---------------------------------------------------------------------------
# Emergency stop / resume tasks (triggered by Slack /agent commands)
# ---------------------------------------------------------------------------
@celery_app.task(name="agent.tasks.daily_skills.set_emergency_stop")
def set_emergency_stop(stop: bool = True) -> dict:
    """Set or clear the emergency stop flag in Redis."""
    try:
        r = _redis()
        if stop:
            r.set(_STOP_FLAG_KEY, "1", ex=86400)
            msg = ":stop_sign: *Emergency stop activated.* Scheduled skills are paused."
        else:
            r.delete(_STOP_FLAG_KEY)
            msg = ":white_check_mark: *Emergency stop cleared.* Scheduled skills will resume."
        _post_to_slack(msg)
        logger.info("emergency_stop_changed", stop=stop)
        return {"status": "ok", "stop": stop}
    except Exception as exc:
        logger.error("emergency_stop_error", error=str(exc))
        return {"status": "error", "error": str(exc)}


@celery_app.task(name="agent.tasks.daily_skills.get_budget_status")
def get_budget_status() -> dict:
    """Return today's spend vs budget — used by Slack /agent budget command."""
    settings = get_settings()
    budget = getattr(settings, "daily_api_budget_usd", 2.00)
    spend = _get_spend_usd()
    stopped = _is_stopped()
    return {
        "spend_usd": spend,
        "budget_usd": budget,
        "remaining_usd": max(0.0, budget - spend),
        "pct_used": (spend / budget * 100) if budget > 0 else 0,
        "emergency_stop": stopped,
    }
