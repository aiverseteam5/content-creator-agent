"""Slack bot: receives commands, runs pipeline in background, handles approval."""

from __future__ import annotations

import threading

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from agent.core.config import get_settings
from agent.core.logging import get_logger
from agent.generators import GeneratedPost

logger = get_logger(__name__)

# In-memory store: Slack message ts -> list of GeneratedPost pending approval
_pending_approvals: dict[str, list[GeneratedPost]] = {}
_approval_lock = threading.Lock()

TRIGGER_KEYWORDS = ("research", "post", "create", "generate", "news", "ai news", "write", "about", "highlights")

# Words to strip when extracting the topic from the user's message
_STRIP_PHRASES = (
    "can you", "please", "do a", "do", "research on", "research about", "research",
    "post about", "post on", "post", "write about", "write a post about", "write",
    "create a post about", "create a post on", "create",
    "generate a post about", "generate",
    "add the key highlights", "add key highlights", "key highlights",
    "and post", "and publish", "and share",
    "top 3 news on", "top 3", "top news on", "top news from",
    "latest news on", "latest news from", "latest news",
    "news on", "news from", "news about",
    "tomorrow", "today", "tonight", "scheduled", "schedule",
)

import re  # noqa: E402

_SCHEDULE_RE = re.compile(
    r"(tomorrow|today|tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"[\s,at]*(\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm)?\s*(?:ist|utc|gmt|pst|est)?)",
    re.IGNORECASE,
)


def _extract_topic(raw_text: str) -> str | None:
    """Strip command words and return the core topic the user cares about."""
    text = raw_text.lower().strip()
    # Remove trigger/command phrases
    for phrase in sorted(_STRIP_PHRASES, key=len, reverse=True):
        text = text.replace(phrase, " ")
    # Remove schedule references
    text = _SCHEDULE_RE.sub("", text)
    # Strip leading/trailing filler words
    topic = " ".join(text.split()).strip(" .,!?")
    topic = re.sub(r"^(the|a|an|about|on)\s+", "", topic).strip()
    topic = re.sub(r"\s+(and|the|a)$", "", topic).strip()
    return topic if len(topic) > 3 else None


def _extract_schedule(raw_text: str) -> str | None:
    """Return a human-readable schedule string if the user specified a time."""
    m = _SCHEDULE_RE.search(raw_text)
    if m:
        return f"{m.group(1)} {m.group(2)}".strip()
    return None


# ---------------------------------------------------------------------------
# Pipeline (runs in background thread)
# ---------------------------------------------------------------------------
def _run_pipeline(say, user_text: str = "") -> None:  # type: ignore[type-arg]
    from agent.generators import generate_posts
    from agent.research import fetch_rss_articles

    topic = _extract_topic(user_text)
    schedule = _extract_schedule(user_text)

    focus_msg = f" on *{topic}*" if topic else ""
    say(f":hourglass_flowing_sand: Researching{focus_msg} from RSS feeds…")

    try:
        articles = fetch_rss_articles(max_total=5)
        if not articles:
            say(":warning: No articles found. Check RSS feeds in `config/sources.yaml`.")
            return

        sources_list = ", ".join({a.source for a in articles})
        say(f":newspaper: Found *{len(articles)} articles* from: {sources_list}\nGenerating content with GPT-4o…")

        posts = generate_posts(articles, topic=topic)
        if not posts:
            say(":warning: Content generation failed. Check OpenAI API key and logs.")
            return

        blocks = _build_approval_blocks(posts, articles, schedule=schedule)
        preview_resp = say(blocks=blocks, text="Content ready for approval")
        preview_ts: str = preview_resp.get("ts", "")

        with _approval_lock:
            _pending_approvals[preview_ts] = posts

        logger.info("approval_pending", ts=preview_ts, topic=topic, platforms=[p.platform for p in posts])

    except Exception as exc:
        logger.error("pipeline_error", error=str(exc))
        say(f":x: Pipeline error: `{exc}`")


def _build_approval_blocks(posts: list[GeneratedPost], articles, schedule: str | None = None) -> list[dict]:  # type: ignore[type-arg]
    header_text = ":pencil: Content Draft — Ready for Review"
    if schedule:
        header_text += f"  |  :calendar: Scheduled: {schedule}"
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text, "emoji": True},
        },
        {"type": "divider"},
    ]

    for post in posts:
        label = "LinkedIn" if post.platform == "linkedin" else "Twitter / X"
        emoji = ":linkedin:" if post.platform == "linkedin" else ":bird:"
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{emoji} {label}* _{post.char_count} chars_\n```{post.body}```",
                },
            }
        )
        blocks.append({"type": "divider"})

    # Sources
    source_lines = "\n".join(f"• <{a.url}|{a.title}> — _{a.source}_" for a in articles)
    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Sources used:*\n{source_lines}"},
        }
    )
    blocks.append({"type": "divider"})

    # Action buttons
    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Approve & Publish", "emoji": True},
                    "style": "primary",
                    "action_id": "approve_post",
                    "value": "approve",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Reject", "emoji": True},
                    "style": "danger",
                    "action_id": "reject_post",
                    "value": "reject",
                },
            ],
        }
    )
    return blocks


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_slack_app() -> App:
    settings = get_settings()
    app = App(token=settings.slack_bot_token)

    @app.event("message")
    def handle_message(event: dict, say) -> None:  # type: ignore[no-untyped-def]
        if event.get("subtype") == "bot_message" or event.get("bot_id"):
            return

        user = event.get("user", "unknown")
        text = event.get("text", "").lower()
        channel = event.get("channel", "")

        logger.info("slack_message_received", user=user, channel=channel, text=text)

        if any(kw in text for kw in TRIGGER_KEYWORDS):
            original_text = event.get("text", "")
            threading.Thread(target=_run_pipeline, args=(say, original_text), daemon=True).start()
        else:
            say(
                f"Hi <@{user}>! Send a message like *research AI news and post* or "
                "*post about NVIDIA GTC highlights* to start the pipeline."
            )

    @app.event("app_mention")
    def handle_mention(event: dict, say) -> None:  # type: ignore[no-untyped-def]
        user = event.get("user", "unknown")
        original_text = event.get("text", "")
        logger.info("slack_mention_received", user=user, text=original_text)
        threading.Thread(target=_run_pipeline, args=(say, original_text), daemon=True).start()

    @app.action("approve_post")
    def handle_approve(ack, body, say, client) -> None:  # type: ignore[no-untyped-def]
        ack()
        message_ts: str = body.get("message", {}).get("ts", "")
        channel_id: str = body.get("channel", {}).get("id", "")
        user: str = body.get("user", {}).get("name", "unknown")

        with _approval_lock:
            posts = _pending_approvals.pop(message_ts, None)

        if posts is None:
            say(":warning: This approval has already been processed or expired.")
            return

        say(f":rocket: <@{user}> approved! Publishing to all platforms…")

        # Collapse the approval message
        try:
            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=":white_check_mark: Approved — publishing in progress.",
                blocks=[],
            )
        except Exception as exc:
            logger.warning("approve_update_failed", error=str(exc))

        def _publish() -> None:
            from agent.publishers import publish_all
            results = publish_all(posts)
            lines = []
            for platform, post_id in results.items():
                if post_id.startswith("ERROR"):
                    lines.append(f":x: *{platform.capitalize()}*: {post_id}")
                else:
                    if platform == "twitter":
                        link = f"https://twitter.com/i/web/status/{post_id}"
                        lines.append(f":white_check_mark: *Twitter/X*: <{link}|View tweet>")
                    else:
                        lines.append(f":white_check_mark: *LinkedIn*: Post published (`{post_id}`)")
            say("\n".join(lines) if lines else ":white_check_mark: Published successfully.")

        threading.Thread(target=_publish, daemon=True).start()

    @app.action("reject_post")
    def handle_reject(ack, body, say, client) -> None:  # type: ignore[no-untyped-def]
        ack()
        message_ts: str = body.get("message", {}).get("ts", "")
        channel_id: str = body.get("channel", {}).get("id", "")
        user: str = body.get("user", {}).get("name", "unknown")

        with _approval_lock:
            _pending_approvals.pop(message_ts, None)

        say(f":no_entry: <@{user}> rejected this draft. Nothing was published.\nSend *research AI news and post* to generate a new draft.")

        try:
            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=":no_entry: Rejected.",
                blocks=[],
            )
        except Exception as exc:
            logger.warning("reject_update_failed", error=str(exc))

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def _run_handler(handler: SocketModeHandler) -> None:
    try:
        handler.start()
    except ValueError as exc:
        if "signal only works in main thread" not in str(exc):
            logger.error("slack_bot_error", error=str(exc))
    except Exception as exc:
        logger.error("slack_bot_error", error=str(exc))


def start_slack_bot() -> None:
    settings = get_settings()
    if not settings.slack_app_token or settings.slack_app_token in ("xapp-...", ""):
        logger.warning("slack_bot_skipped", reason="SLACK_APP_TOKEN not configured")
        return

    app = create_slack_app()
    handler = SocketModeHandler(app, settings.slack_app_token)
    threading.Thread(target=_run_handler, args=(handler,), daemon=True).start()
    logger.info("slack_bot_started", mode="socket")
