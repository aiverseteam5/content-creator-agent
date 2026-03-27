"""Generator module: use GPT-4o to create platform-specific posts from research."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from openai import OpenAI

from agent.core.config import (
    get_brand_config,
    get_platforms_config,
    get_settings,
)
from agent.core.logging import get_logger

if TYPE_CHECKING:
    from agent.research import ArticleResult

logger = get_logger(__name__)


@dataclass
class GeneratedPost:
    platform: str  # "linkedin" | "twitter"
    body: str
    char_count: int


def _build_system_prompt(brand: dict) -> str:
    b = brand.get("brand", {})
    voice = b.get("voice", {})
    avoid = b.get("avoid", {})
    style_notes = "\n".join(f"- {n}" for n in voice.get("style_notes", []))
    avoid_phrases = ", ".join(f'"{p}"' for p in avoid.get("phrases", []))
    return (
        f"You are the social media voice for {b.get('name', 'the brand')}.\n"
        f"Tone: {voice.get('tone', '')}\n"
        f"Style rules:\n{style_notes}\n"
        f"Never use these phrases: {avoid_phrases}\n"
        "Write in first-person plural ('we'/'our'). Output ONLY the post body, no extra commentary."
    )


def _truncate_to_limit(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    for sep in (". ", ".\n", "! ", "? "):
        pos = truncated.rfind(sep)
        if pos != -1:
            return truncated[: pos + 1]
    return truncated.rstrip()


def generate_posts(
    articles: list[ArticleResult],
    topic: str | None = None,
) -> list[GeneratedPost]:
    """Generate LinkedIn and Twitter posts from research articles.

    Args:
        articles: RSS articles fetched by the research module.
        topic: Optional user-specified focus (e.g. "NVIDIA GTC key highlights").
               When provided, GPT-4o focuses the post on this topic even if the
               articles don't directly cover it.
    """
    settings = get_settings()
    brand = get_brand_config()
    platforms = get_platforms_config()

    client = OpenAI(api_key=settings.openai_api_key)
    system_prompt = _build_system_prompt(brand)

    article_block = "\n\n".join(
        f"[{i + 1}] {a.title}\nSource: {a.source}\nURL: {a.url}\nSummary: {a.summary}" for i, a in enumerate(articles)
    )

    # Topic focus instruction prepended when user gave a specific subject
    topic_instruction = (
        f"The user specifically wants content focused on: *{topic}*.\n"
        "Prioritise this topic. Use the articles below for supporting context, "
        "data points, and quotes where relevant — but the post must centre on the requested topic.\n\n"
        if topic
        else ""
    )

    platform_specs = {
        "linkedin": {
            "max": platforms["linkedin"]["max_length"],
            "instruction": (
                f"Write a LinkedIn post ({platforms['linkedin']['min_length']}-"
                f"{platforms['linkedin']['max_length']} chars). "
                "Use line breaks for scannability. "
                f"End with {platforms['linkedin']['hashtag_count'][0]}-"
                f"{platforms['linkedin']['hashtag_count'][1]} relevant hashtags on a new line."
            ),
        },
        "twitter": {
            "max": platforms["twitter"]["max_length"],
            "instruction": (
                f"Write a single tweet (max {platforms['twitter']['max_length']} chars). "
                "Be punchy and direct. End with 1-2 hashtags."
            ),
        },
    }

    results: list[GeneratedPost] = []

    for platform, spec in platform_specs.items():
        user_prompt = f"{topic_instruction}{spec['instruction']}\n\nReference articles:\n\n{article_block}"
        try:
            response = client.chat.completions.create(
                model=settings.default_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=800,
            )
            body = (response.choices[0].message.content or "").strip()
            body = _truncate_to_limit(body, spec["max"])
            results.append(GeneratedPost(platform=platform, body=body, char_count=len(body)))
            logger.info("post_generated", platform=platform, chars=len(body), topic=topic or "general")
        except Exception as exc:
            logger.error("post_generation_failed", platform=platform, error=str(exc))

    return results
