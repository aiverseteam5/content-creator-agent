"""TrendScanSkill — search the web for trending topics and return a digest."""

from __future__ import annotations

from agent.core.logging import get_logger
from agent.skills.base import Skill, SkillResult
from agent.sources.web_search import build_queries, search_web

logger = get_logger(__name__)


class TrendScanSkill(Skill):
    name = "trend_scan"
    description = "Search the web for trending AI/tech topics and return a ranked digest"

    def execute(self, context: dict) -> SkillResult:
        topic: str | None = context.get("topic")
        limit: int = int(context.get("params", {}).get("limit", 5))

        queries = build_queries(topic)
        results = search_web(queries, max_results_per_query=3)

        if not results:
            return SkillResult(
                success=False,
                output=[],
                message=":warning: No results found. Check `TAVILY_API_KEY` or try a different topic.",
                next_action="notify",
            )

        # Deduplicate and take top N
        seen: set[str] = set()
        unique = []
        for r in results:
            key = (r.url or r.title).lower()
            if key not in seen:
                seen.add(key)
                unique.append(r)
            if len(unique) >= limit:
                break

        lines = [f":mag: *Trending: {topic or 'AI & Tech'}*\n"]
        for i, r in enumerate(unique, 1):
            url_part = f" — <{r.url}|link>" if r.url else ""
            lines.append(f"{i}. *{r.title}*{url_part}\n   _{r.summary[:150]}…_")

        logger.info("trend_scan_complete", topic=topic, results=len(unique))

        return SkillResult(
            success=True,
            output=unique,
            message="\n".join(lines),
            next_action="notify",
        )
