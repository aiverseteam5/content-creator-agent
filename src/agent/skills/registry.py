"""SkillRegistry — discovers all skills and routes execution by name."""

from __future__ import annotations

from agent.core.logging import get_logger
from agent.skills.base import Skill, SkillResult
from agent.skills.daily_review import DailyReviewSkill
from agent.skills.trend_scan import TrendScanSkill
from agent.skills.write_post import WritePostSkill

logger = get_logger(__name__)

# Register all available skills here
_SKILLS: list[Skill] = [
    TrendScanSkill(),
    WritePostSkill(),
    DailyReviewSkill(),
]

_REGISTRY: dict[str, Skill] = {s.name: s for s in _SKILLS}


def list_skills() -> list[Skill]:
    """Return all registered skills."""
    return list(_REGISTRY.values())


def get_skill(name: str) -> Skill | None:
    """Return skill by name, or None if not found."""
    return _REGISTRY.get(name)


def execute_skill(name: str, context: dict) -> SkillResult:
    """Execute a skill by name. Returns an error SkillResult if not found."""
    skill = get_skill(name)
    if skill is None:
        available = ", ".join(f"`{s.name}`" for s in _SKILLS)
        return SkillResult(
            success=False,
            output=None,
            message=f":x: Unknown skill `{name}`. Available: {available}",
            next_action="notify",
        )
    logger.info("skill_executing", name=name, context_keys=list(context.keys()))
    try:
        return skill.execute(context)
    except Exception as exc:
        logger.error("skill_execution_error", name=name, error=str(exc))
        return SkillResult(
            success=False,
            output=None,
            message=f":x: Skill `{name}` failed: `{exc}`",
            next_action="notify",
        )
