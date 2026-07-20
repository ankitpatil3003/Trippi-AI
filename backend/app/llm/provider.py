from __future__ import annotations

import re
from datetime import date, timedelta

from app.config import get_settings
from app.schemas.trip import TripConstraints


def _extract_dates(prompt: str) -> tuple[str | None, str | None]:
    # ISO dates
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


async def parse_constraints(
    prompt: str,
    city: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    party_size: int = 2,
    preferences: list[str] | None = None,
) -> TripConstraints:
    """Parse trip constraints via OpenAI when configured, else heuristics."""
    settings = get_settings()
    base = heuristic_parse(prompt, city, start_date, end_date, party_size, preferences)
    if not settings.openai_api_key or settings.llm_provider == "heuristic":
        return base
    try:
        from langchain_openai import ChatOpenAI
        from pydantic import BaseModel, Field

        class LLMConstraints(BaseModel):
            city: str = Field(description="Destination city")
            start_date: str = Field(description="YYYY-MM-DD")
            end_date: str = Field(description="YYYY-MM-DD")
            party_size: int = 2
            preferences: list[str] = Field(default_factory=list)
            avoid: list[str] = Field(default_factory=list)

        llm = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0)
        structured = llm.with_structured_output(LLMConstraints)
        result = await structured.ainvoke(
            [
                (
                    "system",
                    "Extract travel planning constraints. Dates must be YYYY-MM-DD. "
                    "If missing, keep reasonable defaults from the user message.",
                ),
                ("human", prompt),
            ]
        )
        return TripConstraints(
            city=city or result.city or base.city,
            start_date=start_date or result.start_date or base.start_date,
            end_date=end_date or result.end_date or base.end_date,
            party_size=party_size or result.party_size,
            preferences=preferences or result.preferences or base.preferences,
            avoid=result.avoid,
        )
    except Exception:
        return base
