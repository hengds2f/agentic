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
            adults = updated_trip.get('num_adults', 1)
            children = updated_trip.get('num_children', 0)
            pax = f"{adults} adult{'s' if adults != 1 else ''}"
            if children > 0:
                pax += f" and {children} child{'ren' if children != 1 else ''}"
            reply = (
                f"Great! I have everything I need to plan your trip to **{updated_trip.get('destination', '')}** "
                f"from {updated_trip.get('start_date', '?')} to {updated_trip.get('end_date', '?')}. "
                f"Travelers: {pax}. "
                f"Let me search for the best options and show you the cost breakdown..."
            )
        else:
            prompts = {
                "destination": "Where would you like to go?",
                "origin": "Where will you be traveling from? (city and country)",
                "start_date": "What are your travel dates? (start date)",
                "end_date": "And your return date?",
                "num_adults": "How many people are going? (e.g. 2 adults, 1 child)",
            }
            questions = [prompts.get(f, f"Could you tell me about {f}?") for f in missing[:1]]
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

        # Detect budget — accept "$3000", "3000", "3,000", "budget 3000", etc.
        import re
        budget_match = re.search(r'\$\s*([\d,]+)', message)
        if not budget_match:
            budget_match = re.search(r'(?:budget\s*(?:is|of|:)?\s*)([\d,]+)', message, re.IGNORECASE)
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

        # Detect number of travelers: "2 adults", "3 adults 2 children", "5 people", etc.
        adults_match = re.search(r'(\d+)\s*adults?', message, re.IGNORECASE)
        children_match = re.search(r'(\d+)\s*(?:children|child|kids?)', message, re.IGNORECASE)
        people_match = re.search(r'(\d+)\s*(?:people|persons?|pax|travelers?|travellers?)', message, re.IGNORECASE)
        if adults_match:
            updated["num_adults"] = int(adults_match.group(1))
        if children_match:
            updated["num_children"] = int(children_match.group(1))
        if people_match and not adults_match:
            updated["num_adults"] = int(people_match.group(1))

        # Bare number fallback: when message is just a small number (1-20) and
        # num_adults hasn't been set yet, treat it as the traveler count.
        if not updated.get("num_adults"):
            bare = message.strip().replace(',', '')
            if re.fullmatch(r'\d+', bare) and 1 <= int(bare) <= 20:
                updated["num_adults"] = int(bare)

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

        # ── Bare-text fallback for origin ──
        # If destination was already set BEFORE this message, origin is missing,
        # and the message is a simple place name, treat it as the origin.
        # Important: only if destination was NOT just set by this same message.
        dest_was_already_set = bool(trip.get("destination"))
        if dest_was_already_set and updated.get("destination") and not updated.get("origin"):
            stripped = message.strip().rstrip('.!?')
            has_budget = bool(budget_match)
            has_dates = bool(date_matches)
            has_keyword = any(kw in msg for kw in ["budget", "date", "traveler", "adult", "child", "people"])
            if stripped and not has_budget and not has_dates and not has_keyword:
                clean = re.sub(r'^(?:from\s+)', '', stripped, flags=re.IGNORECASE).strip()
                if clean and len(clean) > 1:
                    updated["origin"] = clean.title()

        return updated

    def _check_missing(self, trip: dict) -> list[str]:
        required = ["destination", "origin", "start_date", "end_date", "num_adults"]
        missing = []
        for f in required:
            val = trip.get(f)
            if val is None or val == "" or val == 0:
                missing.append(f)
        return missing
