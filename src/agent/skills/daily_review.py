"""DailyReviewSkill — morning performance briefing from the database."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from agent.core.logging import get_logger
from agent.skills.base import Skill, SkillResult

logger = get_logger(__name__)


class DailyReviewSkill(Skill):
    name = "daily_review"
    description = "Morning summary of yesterday's post performance"

    def execute(self, context: dict) -> SkillResult:
        try:
            return self._build_review(context)
        except Exception as exc:
            logger.error("daily_review_error", error=str(exc))
            return SkillResult(
                success=False,
                output=None,
                message=f":x: Daily review failed: `{exc}`",
                next_action="notify",
            )

    def _build_review(self, context: dict) -> SkillResult:
        import asyncio

        from sqlalchemy import select, func
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker

        from agent.core.config import get_settings
        from agent.core.models import ContentItem, PostPerformance

        settings = get_settings()

        async def _query() -> list[dict]:
            engine = create_async_engine(settings.database_url, echo=False)
            async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

            yesterday_start = (datetime.now(timezone.utc) - timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            yesterday_end = yesterday_start + timedelta(days=1)

            async with async_session() as session:
                stmt = (
                    select(
                        ContentItem.platform,
                        ContentItem.body,
                        ContentItem.published_at,
                        func.max(PostPerformance.impressions).label("impressions"),
                        func.max(PostPerformance.likes).label("likes"),
                        func.max(PostPerformance.shares).label("shares"),
                        func.max(PostPerformance.comments).label("comments"),
                        func.max(PostPerformance.engagement_rate).label("engagement_rate"),
                    )
                    .join(
                        PostPerformance,
                        PostPerformance.content_item_id == ContentItem.id,
                        isouter=True,
                    )
                    .where(
                        ContentItem.published_at >= yesterday_start,
                        ContentItem.published_at < yesterday_end,
                        ContentItem.status == "published",
                    )
                    .group_by(
                        ContentItem.id,
                        ContentItem.platform,
                        ContentItem.body,
                        ContentItem.published_at,
                    )
                    .order_by(ContentItem.published_at.desc())
                )
                result = await session.execute(stmt)
                rows = result.all()
            await engine.dispose()
            return [
                {
                    "platform": r.platform,
                    "body": r.body,
                    "published_at": r.published_at,
                    "impressions": r.impressions or 0,
                    "likes": r.likes or 0,
                    "shares": r.shares or 0,
                    "comments": r.comments or 0,
                    "engagement_rate": r.engagement_rate or 0.0,
                }
                for r in rows
            ]

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    rows = pool.submit(asyncio.run, _query()).result()
            else:
                rows = asyncio.run(_query())
        except Exception as exc:
            logger.warning("daily_review_db_unavailable", error=str(exc))
            rows = []

        return self._format_review(rows)

    def _format_review(self, rows: list[dict]) -> SkillResult:
        today = datetime.now().strftime("%A, %d %b %Y")

        if not rows:
            msg = (
                f":sunny: *Daily Review — {today}*\n\n"
                ":bar_chart: No posts published yesterday. Nothing to report yet.\n"
                "_Tip: trigger `research AI news and post` to start creating content._"
            )
            return SkillResult(success=True, output=[], message=msg, next_action="notify")

        lines = [f":sunny: *Daily Review — {today}*\n"]

        total_impressions = sum(r["impressions"] for r in rows)
        total_likes = sum(r["likes"] for r in rows)
        total_shares = sum(r["shares"] for r in rows)
        avg_engagement = (
            sum(r["engagement_rate"] for r in rows) / len(rows) if rows else 0.0
        )

        lines.append(
            f":chart_with_upwards_trend: *Yesterday at a glance*  "
            f"({len(rows)} post{'s' if len(rows) != 1 else ''})\n"
            f"• Impressions: *{total_impressions:,}*\n"
            f"• Likes: *{total_likes:,}*   Shares: *{total_shares:,}*\n"
            f"• Avg engagement rate: *{avg_engagement:.2%}*\n"
        )

        # Best performing post
        best = max(rows, key=lambda r: r["engagement_rate"])
        platform_emoji = ":linkedin:" if best["platform"] == "linkedin" else ":bird:"
        snippet = best["body"][:120].replace("\n", " ") + ("…" if len(best["body"]) > 120 else "")
        lines.append(
            f":trophy: *Top post* ({platform_emoji} {best['platform'].capitalize()})\n"
            f"_{snippet}_\n"
            f"↳ {best['engagement_rate']:.2%} engagement  |  "
            f"{best['impressions']:,} impressions  |  {best['likes']:,} likes"
        )

        # Per-post breakdown
        lines.append("\n:notepad_spiral: *Post breakdown:*")
        for i, r in enumerate(rows, 1):
            p_emoji = ":linkedin:" if r["platform"] == "linkedin" else ":bird:"
            pub_time = r["published_at"].strftime("%H:%M") if r["published_at"] else "?"
            lines.append(
                f"{i}. {p_emoji} *{r['platform'].capitalize()}* @ {pub_time} UTC — "
                f"{r['impressions']:,} impr · {r['likes']:,} ♥ · "
                f"{r['engagement_rate']:.2%} eng"
            )

        message = "\n".join(lines)
        logger.info("daily_review_complete", posts=len(rows), total_impressions=total_impressions)

        return SkillResult(
            success=True,
            output=rows,
            message=message,
            next_action="notify",
        )
