"""Base agent class — every specialized agent inherits from this."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from app.core.logging import get_logger
from app.models.schemas import AgentRole, ReasoningStep

logger = get_logger(__name__)


class BaseAgent(ABC):
    """All agents share: role, goal, tool list, guardrails, and a run() method."""

    role: AgentRole
    goal: str
    tools: list[str]
    guardrails: list[str]

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's task and return results."""
        ...

    async def execute(self, context: dict[str, Any], trace_id: str = "") -> tuple[dict[str, Any], ReasoningStep]:
        """Wrapper that adds logging, timing, and produces a ReasoningStep."""
        logger.info("agent.start", agent=self.role.value, trace_id=trace_id)
        t0 = time.monotonic()
        try:
            result = await self.run(context)
            elapsed = int((time.monotonic() - t0) * 1000)
            step = ReasoningStep(
                agent=self.role,
                action=self.goal,
                result_summary=result.get("summary", "done"),
                duration_ms=elapsed,
            )
            logger.info("agent.done", agent=self.role.value, elapsed_ms=elapsed, trace_id=trace_id)
            return result, step
        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.error("agent.error", agent=self.role.value, error=str(exc), trace_id=trace_id)
            step = ReasoningStep(
                agent=self.role,
                action=self.goal,
                result_summary=f"Error: {exc}",
                duration_ms=elapsed,
            )
            return {"error": str(exc), "summary": f"Error: {exc}"}, step
