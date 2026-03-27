"""Unit tests for DailyReviewSkill (F15)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from agent.skills.daily_review import DailyReviewSkill


@pytest.fixture
def skill() -> DailyReviewSkill:
    return DailyReviewSkill()


@pytest.fixture
def sample_rows() -> list[dict]:
    return [
        {
            "platform": "linkedin",
            "body": "Excited to share insights on AI agents transforming enterprise workflows.",
            "published_at": datetime(2026, 3, 25, 10, 0, tzinfo=UTC),
            "impressions": 1200,
            "likes": 85,
            "shares": 12,
            "comments": 9,
            "engagement_rate": 0.088,
        },
        {
            "platform": "twitter",
            "body": "AI agents are the future of knowledge work #AI #Automation",
            "published_at": datetime(2026, 3, 25, 10, 5, tzinfo=UTC),
            "impressions": 540,
            "likes": 34,
            "shares": 7,
            "comments": 3,
            "engagement_rate": 0.082,
        },
    ]


class TestSkillMetadata:
    def test_name(self, skill):
        assert skill.name == "daily_review"

    def test_description(self, skill):
        assert "performance" in skill.description.lower() or "morning" in skill.description.lower()


class TestFormatReview:
    def test_empty_rows_returns_no_posts_message(self, skill):
        result = skill._format_review([])
        assert result.success is True
        assert result.next_action == "notify"
        assert "No posts" in result.message or "nothing" in result.message.lower()
        assert result.output == []

    def test_with_rows_success(self, skill, sample_rows):
        result = skill._format_review(sample_rows)
        assert result.success is True
        assert result.next_action == "notify"
        assert result.output == sample_rows

    def test_message_contains_totals(self, skill, sample_rows):
        result = skill._format_review(sample_rows)
        # Total impressions: 1200 + 540 = 1740
        assert "1,740" in result.message or "1740" in result.message

    def test_message_contains_top_post(self, skill, sample_rows):
        result = skill._format_review(sample_rows)
        # LinkedIn has higher engagement (0.088 > 0.082)
        assert "linkedin" in result.message.lower() or "Top post" in result.message

    def test_message_contains_both_platforms(self, skill, sample_rows):
        result = skill._format_review(sample_rows)
        assert "linkedin" in result.message.lower()
        assert "twitter" in result.message.lower()

    def test_single_row(self, skill, sample_rows):
        result = skill._format_review([sample_rows[0]])
        assert result.success is True
        assert "1 post" in result.message or "1,200" in result.message

    def test_engagement_rate_shown_as_percentage(self, skill, sample_rows):
        result = skill._format_review(sample_rows)
        # 8.8% or similar
        assert "%" in result.message


class TestExecute:
    def test_execute_returns_skill_result_when_db_unavailable(self, skill):
        """When DB is unreachable, execute should still succeed with empty data."""
        with patch.object(skill, "_build_review", side_effect=Exception("DB down")):
            result = skill.execute({})
        assert result.success is False
        assert "daily review failed" in result.message.lower() or "DB down" in result.message

    def test_execute_calls_build_review(self, skill):
        mock_result = MagicMock()
        with patch.object(skill, "_build_review", return_value=mock_result) as mock_build:
            result = skill.execute({"some": "context"})
        mock_build.assert_called_once_with({"some": "context"})
        assert result is mock_result
