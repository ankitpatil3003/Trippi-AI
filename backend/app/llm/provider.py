from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta

from pydantic import BaseModel, Field

from app.config import get_settings
from app.llm.factory import get_chat_model, provider_ready
from app.schemas.trip import TripConstraints

logger = logging.getLogger(__name__)


class LLMConstraints(BaseModel):
    city: str = Field(description="Destination city")
    start_date: str = Field(description="YYYY-MM-DD")
    end_date: str = Field(description="YYYY-MM-DD")
    party_size: int = 2
    preferences: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)


def _extract_dates(prompt: str) -> tuple[str | None, str | None]:
    iso = re.findall(r"\d{4}-\d{2}-\d{2}", prompt)
    if len(iso) >= 2:
        return iso[0], iso[1]
    if len(iso) == 1:
        start = date.fromisoformat(iso[0])
        return iso[0], (start + timedelta(days=2)).isoformat()
    return None, None


def _extract_city(prompt: str, fallback: str | None) -> str:
    if fallback:
        return fallback
    patterns = [
        r"\bin\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)",
        r"\bto\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)",
    ]
    for pat in patterns:
        m = re.search(pat, prompt)
        if m:
            city = m.group(1).strip()
            if city.lower() not in {"the", "a", "an", "december", "january"}:
                return city
    return "New York"


def heuristic_parse(
    prompt: str,
    city: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    party_size: int = 2,
    preferences: list[str] | None = None,
) -> TripConstraints:
    d0, d1 = _extract_dates(prompt)
    start = start_date or d0
    end = end_date or d1
    if not start or not end:
        today = date.today() + timedelta(days=1)
        start = start or today.isoformat()
        end = end or (today + timedelta(days=2)).isoformat()
    prefs = list(preferences or [])
    for token in ["views", "pizza", "art", "museum", "food", "family", "nightlife", "history"]:
        if token in prompt.lower() and token not in prefs:
            prefs.append(token)
    return TripConstraints(
        city=_extract_city(prompt, city),
        start_date=start,
        end_date=end,
        party_size=party_size,
        preferences=prefs,
    )


def _parse_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


async def parse_constraints(
    prompt: str,
    city: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    party_size: int = 2,
    preferences: list[str] | None = None,
) -> TripConstraints:
    """Parse trip constraints via Anthropic / OpenRouter / OpenAI, else heuristics."""
    settings = get_settings()
    base = heuristic_parse(prompt, city, start_date, end_date, party_size, preferences)
    if settings.llm_provider == "heuristic" or not provider_ready(settings):
        return base

    system = (
        "Extract travel planning constraints as JSON only. "
        "Dates must be YYYY-MM-DD. "
        "If missing, keep reasonable defaults from the user message. "
        'Schema: {"city":string,"start_date":string,"end_date":string,'
        '"party_size":number,"preferences":string[],"avoid":string[]}'
    )

    try:
        llm = get_chat_model(settings, temperature=0)
        # Prefer structured output when the model supports it; fall back to JSON text.
        try:
            structured = llm.with_structured_output(LLMConstraints)
            result = await structured.ainvoke(
                [
                    ("system", system),
                    ("human", prompt),
                ]
            )
            if isinstance(result, LLMConstraints):
                parsed = result
            else:
                parsed = LLMConstraints.model_validate(result)
        except Exception:
            raw = await llm.ainvoke(
                [
                    ("system", system + " Respond with a single JSON object only."),
                    ("human", prompt),
                ]
            )
            content = raw.content if hasattr(raw, "content") else str(raw)
            if isinstance(content, list):
                content = "".join(
                    block.get("text", "") if isinstance(block, dict) else str(block) for block in content
                )
            parsed = LLMConstraints.model_validate(_parse_json_object(str(content)))

        return TripConstraints(
            city=city or parsed.city or base.city,
            start_date=start_date or parsed.start_date or base.start_date,
            end_date=end_date or parsed.end_date or base.end_date,
            party_size=party_size or parsed.party_size,
            preferences=preferences or parsed.preferences or base.preferences,
            avoid=parsed.avoid,
        )
    except Exception as exc:
        logger.warning("LLM constraint parse failed (%s); using heuristics", exc)
        return base
