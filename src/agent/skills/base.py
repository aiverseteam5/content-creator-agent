"""Skill abstract base class and SkillResult."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SkillResult:
    success: bool
    output: Any                     # Skill-specific payload
    message: str                    # Human-readable Slack summary
    next_action: str | None         # "await_approval" | "notify" | "publish" | None


class Skill(ABC):
    """Base class for all agent skills."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier used to invoke this skill (e.g. 'trend_scan')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line description shown in /agent skills list."""
        ...

    @abstractmethod
    def execute(self, context: dict) -> SkillResult:
        """Run the skill and return a result.

        Args:
            context: Dict with keys like 'topic', 'params', etc.
        """
        ...
