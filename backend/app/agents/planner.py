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
        from_match = re.search(r'from\s+([a-zA-Z\s]+?)(?:\s*,|\s+to\s+|\s*$|\s+\d|\s+budget)', message, re.IGNORECASE)
        if from_match:
            origin_candidate = from_match.group(1).strip()
            if len(origin_candidate) > 1:
                updated["origin"] = origin_candidate.title()

        origin_lower = updated.get("origin", "").lower()

        # Detect destination — accept any place name, not just a hardcoded list
        # Try explicit patterns: "visit X", "go to X", "trip to X", "fly to X", etc.
        to_match = re.search(
            r'(?:heading to|travel to|trip to|fly to|go to|visit)\s+([a-zA-Z\s,]+?)(?:\s+from\s+|\s*$|\s+\d|\s+budget|\s+for\s)',
            message, re.IGNORECASE,
        )
        if not to_match:
            # Fallback: bare "to X" but only when preceded by "want" or similar
            to_match = re.search(
                r'(?:want|like|plan|going)\s+to\s+([a-zA-Z\s,]+?)(?:\s+from\s+|\s*$|\s+\d|\s+budget|\s+for\s)',
                message, re.IGNORECASE,
            )
        if to_match:
            dest_candidate = to_match.group(1).strip().rstrip(',')
            if len(dest_candidate) > 1 and dest_candidate.lower() != origin_lower:
                updated["destination"] = dest_candidate.title()
        elif not updated.get("destination"):
            # If no destination yet and message looks like a simple place name
            # (no budget, no date, no keywords — just a bare destination input)
            stripped = message.strip().rstrip('.!?')
            has_budget = bool(budget_match)
            has_dates = bool(date_matches)
            has_mood = any(m in msg for m in ["relaxing", "romantic", "adventure", "family", "workation", "cultural"])
            has_keyword = any(kw in msg for kw in ["from", "budget", "date", "origin", "traveler"])

            if stripped and not has_budget and not has_dates and not has_mood and not has_keyword:
                # Treat the whole message as a destination
                # Remove common filler words
                clean = re.sub(r'^(?:i\s+want\s+|i\'?d?\s+like\s+|let\'?s?\s+go\s+|how about\s+|maybe\s+)', '', stripped, flags=re.IGNORECASE).strip()
                if clean and len(clean) > 1 and clean.lower() != origin_lower:
                    updated["destination"] = clean.title()

        return updated

    def _check_missing(self, trip: dict) -> list[str]:
        required = ["destination", "start_date", "end_date", "budget_total"]
        return [f for f in required if not trip.get(f)]
