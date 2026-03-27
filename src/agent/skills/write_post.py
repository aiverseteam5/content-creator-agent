"""WritePostSkill — generate LinkedIn + Twitter drafts and send for approval."""

from __future__ import annotations

from agent.core.logging import get_logger
from agent.research import fetch_articles
from agent.skills.base import Skill, SkillResult

logger = get_logger(__name__)


class WritePostSkill(Skill):
    name = "write_post"
    description = "Research a topic and generate LinkedIn + Twitter drafts for approval"

    def execute(self, context: dict) -> SkillResult:
        from agent.generators import generate_posts

        topic: str | None = context.get("topic")

        articles = fetch_articles(topic=topic, max_total=5)
        if not articles:
            return SkillResult(
                success=False,
                output=[],
                message=":warning: No research articles found. Try a different topic.",
                next_action="notify",
            )

        posts = generate_posts(articles, topic=topic)
        if not posts:
            return SkillResult(
                success=False,
                output=[],
                message=":warning: Content generation failed. Check OpenAI API key.",
                next_action="notify",
            )

        logger.info("write_post_skill_complete", topic=topic, platforms=[p.platform for p in posts])

        return SkillResult(
            success=True,
            output={"posts": posts, "articles": articles},
            message=f":pencil: Draft ready for *{topic or 'AI news'}*",
            next_action="await_approval",
        )
