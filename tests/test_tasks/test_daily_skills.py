"""Unit tests for daily_skills Celery task guards (F15)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Import pure helper functions without triggering Celery setup
from agent.tasks import daily_skills as ds


# ---------------------------------------------------------------------------
# Helpers: _is_stopped / _get_spend_usd / _record_spend
# ---------------------------------------------------------------------------

class TestIsStoppedFlag:
    def test_returns_false_when_key_missing(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        with patch.object(ds, "_redis", return_value=mock_redis):
            assert ds._is_stopped() is False

    def test_returns_true_when_key_set(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = "1"
        with patch.object(ds, "_redis", return_value=mock_redis):
            assert ds._is_stopped() is True

    def test_returns_false_on_redis_error(self):
        with patch.object(ds, "_redis", side_effect=Exception("conn refused")):
            assert ds._is_stopped() is False


class TestGetSpendUsd:
    def test_returns_zero_when_key_missing(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        with patch.object(ds, "_redis", return_value=mock_redis):
            assert ds._get_spend_usd() == 0.0

    def test_returns_stored_float(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = "1.23"
        with patch.object(ds, "_redis", return_value=mock_redis):
            assert ds._get_spend_usd() == pytest.approx(1.23)

    def test_returns_zero_on_error(self):
        with patch.object(ds, "_redis", side_effect=Exception("boom")):
            assert ds._get_spend_usd() == 0.0


class TestRecordSpend:
    def test_increments_key_and_returns_new_total(self):
        mock_redis = MagicMock()
        pipe = MagicMock()
        pipe.execute.return_value = ["0.020"]
        mock_redis.pipeline.return_value = pipe
        with patch.object(ds, "_redis", return_value=mock_redis):
            total = ds._record_spend(0.020)
        assert total == pytest.approx(0.020)
        pipe.incrbyfloat.assert_called_once()
        pipe.expire.assert_called_once()

    def test_returns_zero_on_error(self):
        with patch.object(ds, "_redis", side_effect=Exception("boom")):
            assert ds._record_spend(1.0) == 0.0


# ---------------------------------------------------------------------------
# run_scheduled_skill guards
# ---------------------------------------------------------------------------

class TestRunScheduledSkillGuards:
    """Test the three guards without actually running a skill."""

    def _make_task(self):
        """Get the Celery task function unwrapped (call the underlying function)."""
        return ds.run_scheduled_skill

    def test_emergency_stop_returns_stopped(self):
        with patch.object(ds, "_is_stopped", return_value=True):
            result = ds.run_scheduled_skill.run("trend_scan")
        assert result["status"] == "stopped"
        assert result["skill"] == "trend_scan"

    def test_idempotency_skips_if_already_ran(self):
        mock_redis = MagicMock()
        # nx=True returns None (key already existed → set returns None)
        mock_redis.set.return_value = None
        with (
            patch.object(ds, "_is_stopped", return_value=False),
            patch.object(ds, "_redis", return_value=mock_redis),
        ):
            result = ds.run_scheduled_skill.run("trend_scan")
        assert result["status"] == "skipped_idempotent"

    def test_budget_cap_blocks_skill(self):
        mock_redis = MagicMock()
        mock_redis.set.return_value = True  # idempotency: first run

        mock_settings = MagicMock()
        mock_settings.daily_api_budget_usd = 2.00

        with (
            patch.object(ds, "_is_stopped", return_value=False),
            patch.object(ds, "_redis", return_value=mock_redis),
            patch.object(ds, "_get_spend_usd", return_value=2.50),  # over budget
            patch("agent.tasks.daily_skills.get_settings", return_value=mock_settings),
            patch.object(ds, "_post_to_slack"),
        ):
            result = ds.run_scheduled_skill.run("trend_scan")
        assert result["status"] == "budget_cap"
        assert result["spend_usd"] == 2.50

    def test_happy_path_executes_skill_and_records_spend(self):
        mock_redis = MagicMock()
        mock_redis.set.return_value = True

        mock_settings = MagicMock()
        mock_settings.daily_api_budget_usd = 2.00

        mock_skill_result = MagicMock()
        mock_skill_result.success = True
        mock_skill_result.message = "All good"

        with (
            patch.object(ds, "_is_stopped", return_value=False),
            patch.object(ds, "_redis", return_value=mock_redis),
            patch.object(ds, "_get_spend_usd", return_value=0.0),
            patch("agent.tasks.daily_skills.get_settings", return_value=mock_settings),
            patch("agent.skills.registry.execute_skill", return_value=mock_skill_result),
            patch.object(ds, "_record_spend", return_value=0.02),
            patch.object(ds, "_post_to_slack") as mock_post,
        ):
            result = ds.run_scheduled_skill.run("trend_scan", {})

        assert result["status"] == "ok"
        assert result["skill"] == "trend_scan"
        mock_post.assert_called_once_with("All good")


# ---------------------------------------------------------------------------
# get_budget_status
# ---------------------------------------------------------------------------

class TestGetBudgetStatus:
    def test_returns_expected_keys(self):
        mock_settings = MagicMock()
        mock_settings.daily_api_budget_usd = 2.00
        with (
            patch("agent.tasks.daily_skills.get_settings", return_value=mock_settings),
            patch.object(ds, "_get_spend_usd", return_value=0.50),
            patch.object(ds, "_is_stopped", return_value=False),
        ):
            status = ds.get_budget_status()

        assert status["spend_usd"] == pytest.approx(0.50)
        assert status["budget_usd"] == pytest.approx(2.00)
        assert status["remaining_usd"] == pytest.approx(1.50)
        assert status["pct_used"] == pytest.approx(25.0)
        assert status["emergency_stop"] is False

    def test_remaining_never_negative(self):
        mock_settings = MagicMock()
        mock_settings.daily_api_budget_usd = 2.00
        with (
            patch("agent.tasks.daily_skills.get_settings", return_value=mock_settings),
            patch.object(ds, "_get_spend_usd", return_value=5.00),
            patch.object(ds, "_is_stopped", return_value=True),
        ):
            status = ds.get_budget_status()
        assert status["remaining_usd"] == 0.0
        assert status["emergency_stop"] is True
