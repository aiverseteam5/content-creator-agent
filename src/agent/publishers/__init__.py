"""Publishers: post approved content to Twitter/X and LinkedIn."""

from __future__ import annotations

import httpx
import tweepy

from agent.core.config import get_settings
from agent.core.logging import get_logger
from agent.generators import GeneratedPost

logger = get_logger(__name__)


def publish_twitter(post: GeneratedPost) -> str:
    """Post a tweet via Tweepy OAuth 1.0a. Returns the tweet ID."""
    settings = get_settings()
    client = tweepy.Client(
        consumer_key=settings.twitter_api_key,
        consumer_secret=settings.twitter_api_secret,
        access_token=settings.twitter_access_token,
        access_token_secret=settings.twitter_access_token_secret,
    )
    try:
        response = client.create_tweet(text=post.body)
        tweet_id: str = str(response.data["id"])
        logger.info("twitter_published", tweet_id=tweet_id, chars=post.char_count)
        return tweet_id
    except tweepy.TweepyException as exc:
        logger.error("twitter_publish_failed", error=str(exc))
        raise RuntimeError(f"Twitter publish failed: {exc}") from exc


def publish_linkedin(post: GeneratedPost) -> str:
    """Post to LinkedIn via the UGC Posts v2 API. Returns the post URN."""
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.linkedin_access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    payload = {
        "author": settings.linkedin_person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": post.body},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    try:
        with httpx.Client(timeout=15.0) as http:
            resp = http.post("https://api.linkedin.com/v2/ugcPosts", headers=headers, json=payload)
            resp.raise_for_status()
        post_urn: str = resp.headers.get("x-restli-id", "unknown")
        logger.info("linkedin_published", post_urn=post_urn, chars=post.char_count)
        return post_urn
    except httpx.HTTPStatusError as exc:
        logger.error("linkedin_publish_failed", status=exc.response.status_code, body=exc.response.text)
        raise RuntimeError(
            f"LinkedIn publish failed [{exc.response.status_code}]: {exc.response.text}"
        ) from exc


def publish_all(posts: list[GeneratedPost]) -> dict[str, str]:
    """Publish all generated posts. Returns platform -> post_id (or error string)."""
    results: dict[str, str] = {}
    for post in posts:
        try:
            if post.platform == "twitter":
                results["twitter"] = publish_twitter(post)
            elif post.platform == "linkedin":
                results["linkedin"] = publish_linkedin(post)
        except RuntimeError as exc:
            results[post.platform] = f"ERROR: {exc}"
    return results
