"""Planner Agent — conversational intake, clarification, trip extraction."""
from __future__ import annotations

import json
from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentRole


class PlannerAgent(BaseAgent):
    role = AgentRole.planner
    goal = "Collect trip requirements conversationally and determine readiness to plan"
    tools = ["extract_trip_info", "ask_clarification"]
    guardrails = ["Never fabricate destinations", "Ask if key info is missing"]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        trip = context.get("trip", {})
        user_message = context.get("user_message", "")
        history = context.get("history", [])

        # Extract trip fields from the user message
        updated_trip = self._extract_fields(user_message, trip)

        # Check completeness
        missing = self._check_missing(updated_trip)
        ready = len(missing) == 0

        if ready:
            reply = (
                f"Great! I have everything I need to plan your trip to **{updated_trip.get('destination', '')}** "
                f"from {updated_trip.get('start_date', '?')} to {updated_trip.get('end_date', '?')}. "
                f"Budget: ${updated_trip.get('budget_total', 0):,.0f}. "
                f"Let me search for the best options now..."
            )
        else:
            prompts = {
                "destination": "Where would you like to go?",
                "start_date": "What are your travel dates? (start date)",
                "end_date": "And your return date?",
                "budget_total": "What's your approximate budget for the trip?",
                "origin": "Where will you be traveling from?",
            }
            questions = [prompts.get(f, f"Could you tell me about {f}?") for f in missing[:2]]
            reply = " ".join(questions)

        return {
            "reply": reply,
            "updated_trip": updated_trip,
            "ready_to_plan": ready,
            "missing_fields": missing,
            "summary": f"{'Ready to plan' if ready else f'Missing: {missing}'}",
        }

    def _extract_fields(self, message: str, trip: dict) -> dict:
        """Simple keyword-based extraction (replaced by LLM in production)."""
        updated = dict(trip)
        msg = message.lower()

        # Detect mood
        for mood in ["relaxing", "romantic", "adventure", "family", "workation", "cultural"]:
            if mood in msg:
                updated["mood"] = mood

        # Detect budget
        import re
        budget_match = re.search(r'\$\s*([\d,]+)', message)
        if budget_match:
            updated["budget_total"] = float(budget_match.group(1).replace(",", ""))

        # Detect dates (YYYY-MM-DD)
        date_matches = re.findall(r'\d{4}-\d{2}-\d{2}', message)
        if len(date_matches) >= 2:
            updated["start_date"] = date_matches[0]
            updated["end_date"] = date_matches[1]
        elif len(date_matches) == 1:
            if not updated.get("start_date"):
                updated["start_date"] = date_matches[0]
            else:
                updated["end_date"] = date_matches[0]

        # Detect "from <city>" first so we can exclude origin from destinations
        from_match = re.search(r'from\s+([a-zA-Z\s]+?)(?:\s+to\s+|\s*$|,|\s+\d)', message, re.IGNORECASE)
        if from_match:
            origin_candidate = from_match.group(1).strip()
            if len(origin_candidate) > 1:
                updated["origin"] = origin_candidate.title()

        origin_lower = updated.get("origin", "").lower()

        # Detect common destinations (simple heuristic)
        destinations = [
            "paris", "tokyo", "london", "rome", "barcelona", "new york",
            "bali", "sydney", "dubai", "amsterdam", "lisbon", "bangkok",
            "singapore", "hawaii", "maldives", "iceland", "morocco",
        ]
        # Try "to <dest>" pattern first
        to_match = re.search(r'(?:to|visit|go to|trip to)\s+([a-zA-Z\s]+?)(?:\s+from\s+|\s*$|,|\s+\d)', message, re.IGNORECASE)
        if to_match:
            to_candidate = to_match.group(1).strip().lower()
            for dest in destinations:
                if dest in to_candidate and dest != origin_lower:
                    updated["destination"] = dest.title()
                    break
        else:
            for dest in destinations:
                if dest in msg and dest != origin_lower:
                    updated["destination"] = dest.title()

        return updated

    def _check_missing(self, trip: dict) -> list[str]:
        required = ["destination", "start_date", "end_date", "budget_total"]
        return [f for f in required if not trip.get(f)]
