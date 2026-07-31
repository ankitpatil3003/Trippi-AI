# Trippi-AI Design Spec

Date: 2026-07-20  
Status: Approved for implementation

## 1. Purpose

Trippi-AI is a multi-agent AI travel planner that turns a natural language trip request into a day by day itinerary. It keeps WanderGenie-class core planning (planner, researcher, packager on a shared state graph) while adding weather-aware scheduling through a remote Weather MCP service, soft date postpone/prepone suggestions, and must-try dining picks (one local, one fancy).

Success bar for v1: robust, scalable portfolio-ready demo of the trip planning domain with the weather extension integrated cleanly. Resume text may be updated from measured eval results (never invent percentages).

## 2. Locked decisions

| Area | Choice |
|------|--------|
| Product name / repo | Trippi-AI |
| Backend | Python, FastAPI, LangGraph |
| Frontend | React, Vite, TypeScript (Vercel) |
| LLM | OpenAI gpt-4o-mini primary; provider adapter; optional AWS Bedrock |
| Weather | Remote MCP sidecar (MCP-Weather-Agent mcp-server on Render); Groq stays inside that service |
| Memory | Postgres pgvector + BM25/full text + Neo4j hybrid retrieval |
| Observability | Langfuse per-agent traces |
| Date shift | Soft recommend: always plan requested dates; show suggestion + rebuild |
| Dining | Hybrid retrieval + LLM ranking (not Google Places / Yelp) |
| UI v1 | Core planner UI (no Mapbox routes, calendar export, or booking deep links) |

## 3. Architecture

### 3.1 Runtime graph (Approach 3)

1. Planner parses intent into `TripConstraints`.
2. Fan out in parallel: Researcher (hybrid POI/restaurant retrieval) and Weather (MCP forecast).
3. Join shared `TripState`.
4. WeatherAware Packager builds day schedules (rainy → indoor, clear → outdoor).
5. Dining ranker selects local + fancy must-try and places meal slots.
6. Validator schema-checks and optionally auto-patches once.
7. Soft `DateShiftSuggestion` attached when rain ratio is high.

### 3.2 Deploy topology

1. Deploy Weather MCP (`mcp-server` only) to Render first → `MCP_SERVER_URL`.
2. Deploy Trippi-AI API to Render with `MCP_SERVER_URL`.
3. Deploy Trippi-AI UI to Vercel with `VITE_API_URL`.
4. Managed data: Supabase (or Render Postgres with pgvector) + Neo4j Aura.
5. Local: docker compose for Postgres/pgvector, Neo4j, API, UI; MCP may be local or remote.

Trust boundaries: UI talks only to Trippi-AI API. API never holds `OPENWEATHER_API_KEY`. Weather keys live only in the MCP service.

## 4. Shared state and API

### 4.1 TripState fields

- `raw_prompt`, `constraints` (city, start/end, party, prefs, avoid)
- `pois[]`, `restaurant_candidates[]`
- `weather_by_day[]`, `weather_window_extended[]`
- `date_shift_suggestion` (nullable)
- `itinerary` (day → timed blocks with indoor/outdoor tag)
- `dining_picks` (`local_must_try`, `fancy_must_try` + placement)
- `agent_status[]`, `errors[]`, `eval_run_id`
- `weather_available` (false when MCP fails)

### 4.2 API

- `POST /api/trips/plan` → `{ trip_id }`
- `GET /api/trips/{id}` → full trip JSON
- `GET /api/trips/{id}/status` → agent progress
- `POST /api/trips/{id}/rebuild` → body `{ start, end }` for date shift rebuild

### 4.3 DateShiftSuggestion

- `original_rain_ratio`, `suggested_start`, `suggested_end`, `suggested_rain_ratio`
- `reason`, `direction` (`postpone` | `prepone` | `none`)
- Threshold default: `0.35` (env `DATE_SHIFT_RAIN_RATIO`), scored on continuous
  wetness (mean daily precip probability) rather than a binary rainy day count

## 5. Agents and rules

### 5.1 Weather via MCP

Tools: `geocode_city`, `get_forecast`. Classify each day as `clear` | `mixed` | `rainy`. OpenWeather free forecast horizon is short (about 5 days); UI must state when the trip exceeds forecast coverage.

### 5.2 Packager weather rules

- Rainy: prefer indoor POIs.
- Clear: prefer outdoor sightseeing.
- Mixed: outdoor then indoor (or reverse if hourly hints exist).
- Never leave a day empty; mark `fallback: true` when pools are thin.

### 5.3 Dining

- `local_must_try`: authentic/local, mid price.
- `fancy_must_try`: upscale special occasion.
- Place on lunch/dinner without colliding with major POI blocks.

### 5.4 Failure modes

- MCP down / rate limited: continue without weather adaptation; set `weather_available=false`; no invented forecasts.
- No restaurant candidates: weak grounding fallback with `grounding: "weak"` flagged in UI.
- Schema failure: one auto-patch pass, then return partial trip with structured errors `{ code, message, retryable }`.

## 6. Hybrid retrieval and evaluation

Pipeline: dense (pgvector) + sparse (BM25/full text) + Neo4j expand (`IN_NEIGHBORHOOD`, `SIMILAR_TO`, `SAME_CUISINE`) → reciprocal rank fusion → rerank → tag indoor/outdoor/either.

Offline eval under `backend/evals/retrieval/` compares dense-only vs dense+BM25 vs full hybrid (+ rerank). Metrics: recall@k, nDCG, route coherence. Report only measured numbers.

Langfuse: one trace per plan; spans per agent; log MCP tool calls and retrieval channel counts.

## 7. Frontend v1

- Home: Trippi-AI brand, prompt, city/dates, primary CTA.
- Results: agent status chips, day itinerary with weather badges, dining card, date shift card + rebuild.
- Polling until complete; banners for errors and degraded weather.
- Pixel polish required; fix obvious visual defects when noticed.

## 8. Testing and quality

- Unit: classification, shift scoring, RRF, dining filters, validators.
- Integration: graph with MCP stub and memory fakes.
- E2E (Playwright): user path for plan + forced rainy stub showing shift card. Bug fixes start with E2E reproduction.
- CI: lint, typecheck, pytest; E2E with stubs.
- Docs/comments: avoid em dash and decorative dash punctuation; use commas or colons.
- Never hand-edit CHANGELOG or other auto-generated files.
- Prefer quality, simplicity, robustness, scalability, and long-term maintainability over development cost.

## 9. Repo layout

```
Trippi-AI/
  backend/
  frontend/
  docker-compose.yml
  docs/superpowers/specs/
  README.md
```

## 10. Out of scope for v1

Interactive map routes, Google Calendar / ICS, booking deep links, conversational itinerary swaps, auth, Google Places / Yelp.

## 11. Success criteria

- Natural language → multi-day itinerary with visible agent progress.
- Rainy days skew indoor; clear days outdoor; one local and one fancy dining pick.
- Soft date shift when rain ratio is high; rebuild works.
- Retrieval eval script produces a real comparison artifact.
- Langfuse shows per-agent spans including MCP calls.
- MCP and API on Render; UI on Vercel; local docker compose for development.
