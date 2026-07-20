export type WeatherClass = "clear" | "mixed" | "rainy";

export interface AgentStatus {
  agent: string;
  status: "pending" | "running" | "done" | "error" | "skipped";
  message: string;
}

export interface ItineraryBlock {
  start_time: string;
  end_time: string;
  title: string;
  setting: string;
  notes: string;
  fallback: boolean;
  kind: "poi" | "meal" | "buffer";
}

export interface ItineraryDay {
  date: string;
  weather: WeatherClass | null;
  weather_summary: string;
  blocks: ItineraryBlock[];
}

export interface DiningPick {
  restaurant_id: string;
  name: string;
  cuisine: string;
  price_tier: string;
  day_date: string | null;
  meal_slot: string | null;
  grounding: string;
  reason: string;
}

export interface TripRecord {
  trip_id: string;
  status: string;
  raw_prompt: string;
  constraints: {
    city: string;
    start_date: string;
    end_date: string;
  } | null;
  weather_available: boolean;
  date_shift_suggestion: {
    original_rain_ratio: number;
    suggested_start: string;
    suggested_end: string;
    suggested_rain_ratio: number;
    reason: string;
    direction: "postpone" | "prepone" | "none";
  } | null;
  itinerary: ItineraryDay[];
  dining_picks: {
    local_must_try: DiningPick | null;
    fancy_must_try: DiningPick | null;
  } | null;
  agent_status: AgentStatus[];
  errors: { code: string; message: string; retryable: boolean }[];
}
