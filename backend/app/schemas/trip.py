from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class SettingKind(str, Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    EITHER = "either"


class WeatherClass(str, Enum):
    CLEAR = "clear"
    MIXED = "mixed"
    RAINY = "rainy"


class TripConstraints(BaseModel):
    city: str
    start_date: str
    end_date: str
    party_size: int = 2
    preferences: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    origin: str | None = None


Provenance = Literal["live", "seed"]


class POI(BaseModel):
    id: str
    name: str
    city: str
    description: str = ""
    neighborhood: str = ""
    setting: SettingKind = SettingKind.EITHER
    tags: list[str] = Field(default_factory=list)
    lat: float | None = None
    lon: float | None = None
    score: float = 0.0
    source_urls: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    # Where this record came from. Never present unsourced data as live.
    provenance: Provenance = "seed"


class RestaurantCandidate(BaseModel):
    id: str
    name: str
    city: str
    cuisine: str
    neighborhood: str = ""
    price_tier: Literal["local", "mid", "fancy"] = "mid"
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    score: float = 0.0
    source_urls: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    provenance: Provenance = "seed"


class WeatherDay(BaseModel):
    date: str
    classification: WeatherClass
    summary: str = ""
    precip_probability: float = 0.0
    temp_c: float | None = None


class DateShiftSuggestion(BaseModel):
    original_rain_ratio: float
    suggested_start: str
    suggested_end: str
    suggested_rain_ratio: float
    reason: str
    direction: Literal["postpone", "prepone", "none"] = "none"
    wetness: float = 0.0
    suggested_wetness: float = 0.0
    threshold: float = 0.35
    daily_pops: list[float] = Field(default_factory=list)
    daily_dates: list[str] = Field(default_factory=list)


class ItineraryBlock(BaseModel):
    start_time: str
    end_time: str
    title: str
    poi_id: str | None = None
    setting: SettingKind = SettingKind.EITHER
    notes: str = ""
    fallback: bool = False
    kind: Literal["poi", "meal", "buffer"] = "poi"
    # None for buffer blocks, which are generic time, not a sourced place.
    provenance: Provenance | None = None


class ItineraryDay(BaseModel):
    date: str
    weather: WeatherClass | None = None
    weather_summary: str = ""
    blocks: list[ItineraryBlock] = Field(default_factory=list)


class DiningPick(BaseModel):
    restaurant_id: str
    name: str
    cuisine: str
    price_tier: Literal["local", "mid", "fancy"]
    day_date: str | None = None
    meal_slot: Literal["lunch", "dinner"] | None = None
    grounding: Literal["strong", "weak"] = "strong"
    reason: str = ""
    provenance: Provenance = "seed"


class DiningPicks(BaseModel):
    local_must_try: DiningPick | None = None
    fancy_must_try: DiningPick | None = None


class AgentStatus(BaseModel):
    agent: str
    status: Literal["pending", "running", "done", "error", "skipped"]
    message: str = ""


class TripError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class TripRecord(BaseModel):
    trip_id: str
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    raw_prompt: str = ""
    constraints: TripConstraints | None = None
    pois: list[POI] = Field(default_factory=list)
    restaurant_candidates: list[RestaurantCandidate] = Field(default_factory=list)
    weather_by_day: list[WeatherDay] = Field(default_factory=list)
    weather_window_extended: list[WeatherDay] = Field(default_factory=list)
    weather_available: bool = True
    research_available: bool = True
    dining_available: bool = True
    date_shift_suggestion: DateShiftSuggestion | None = None
    itinerary: list[ItineraryDay] = Field(default_factory=list)
    dining_picks: DiningPicks | None = None
    agent_status: list[AgentStatus] = Field(default_factory=list)
    errors: list[TripError] = Field(default_factory=list)
    eval_run_id: str | None = None
    replan_of: str | None = None
    plan_cycle: int = 1
    meta: dict[str, Any] = Field(default_factory=dict)


class PlanRequest(BaseModel):
    prompt: str
    city: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    party_size: int = 2
    preferences: list[str] = Field(default_factory=list)


class PlanResponse(BaseModel):
    trip_id: str


class RebuildRequest(BaseModel):
    start: str
    end: str


class StatusResponse(BaseModel):
    trip_id: str
    status: str
    agent_status: list[AgentStatus]
    errors: list[TripError] = Field(default_factory=list)
