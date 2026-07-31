# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

The virtualenv lives at the repo root (`.venv`), not inside `backend/`. Run backend commands from `backend/`.

```bash
# Backend (from backend/)
../.venv/Scripts/python.exe -m pytest -q                              # full suite, ~0.4s
../.venv/Scripts/python.exe -m pytest tests/test_date_shift.py -q     # one file
../.venv/Scripts/python.exe -m pytest tests/test_date_shift.py::test_name -q
../.venv/Scripts/python.exe -m ruff check app tests                   # lint (CI runs exactly this)
../.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8080
../.venv/Scripts/python.exe -m evals.retrieval.run_eval               # writes evals/retrieval/results.json

# Frontend (from frontend/)
npm run dev        # Vite on :5173
npm run lint       # tsc --noEmit over src and e2e
npm run build      # tsc --noEmit && vite build
npm run test:e2e   # Playwright; needs the API up with MCP_STUB=true

# Full local stack (Postgres/pgvector + Neo4j + API + UI)
docker compose up
```

`tests/conftest.py` forces `LLM_PROVIDER=heuristic` and the stub flags. Without that,
a developer `.env` with a real OpenRouter key makes every graph test call the live API,
which took the suite from 0.4s to over two minutes and made it fail offline. Do not
remove those assignments to "respect local config"; the point is that tests are hermetic.

If port 8080 is taken locally, set `VITE_PROXY_TARGET` to wherever the API is running.
The dev proxy in `vite.config.ts` reads it.

## Architecture

FastAPI + LangGraph backend, React/Vite frontend, and three remote MCP services. The backend nodes are thin MCP clients; all domain data comes from the MCP services, with local seed data used only as a degraded fallback.

```
planner -> { researcher || weather } -> packager -> dining -> validator
```

Defined in `backend/app/agents/graph.py`. Researcher and Weather fan out in parallel from planner and fan back in at packager.

### Dual state: the non-obvious invariant

Every node writes to **two** places, and both matter:

1. The LangGraph `GraphState` (returned dict), which feeds downstream nodes.
2. The module level `trip_store` singleton (`app/store/trips.py`), via `_set_status()` and `trip_store.save()`.

The HTTP API and the polling UI read **only** `trip_store`. A node that updates `GraphState` but skips `_set_status`/`trip_store.save` will compute correctly and be invisible in the UI. When adding a node, wire both.

Because researcher and weather run concurrently and both append to `agent_status`, that field needs the `Annotated[..., _merge_status]` reducer to avoid clobbering. Any new parallel node writing a shared list field needs the same treatment.

### Sourcing integrity, the hard constraint

Read `docs/INTEGRITY.md` before touching retrieval or the fallback path. The rule that
most affects code: **Trippi never generates a place name.** The fallback previously
built entries by interpolating the city (`"Paris Old Town Walk"`), which shipped
invented recommendations for every city except New York. That path is deleted and
`tests/test_integrity_sourcing.py` guards it.

`app/memory/seed_data.py` serves only what is recorded in `seed_corpus.json`, which is
a snapshot of real API responses produced by `scripts/build_seed_corpus.py`. An unknown
city returns an empty list, and the graph reports that honestly. Empty is a correct
answer; do not "improve" it with generated content.

Every POI, restaurant, itinerary block, and dining pick carries `provenance`
(`live` or `seed`, `None` for buffer blocks), surfaced in the UI.

### MCP degradation contract

Every MCP client (`app/mcp/client.py`, `research.py`, `dining_mcp.py`) returns `(data, available: bool)` and never raises into the graph. On failure it logs a warning and falls back to `app/memory/fusion.py` retrieval over the recorded corpus. Preserve this shape when adding services: the graph assumes it cannot fail.

Chip status distinguishes three cases in the researcher and dining nodes:

- no results at all means `skipped`, with a message naming the city, and this check comes first
- stub flag on, or URL unset, means recorded data was intended, so the chip is `done`
- a service that was configured but failed means `skipped`

Do not collapse these; the UI banners depend on the difference.

`MCP_STUB`, `RESEARCH_MCP_STUB`, and `DINING_MCP_STUB` all default to **true**, so a fresh checkout runs fully offline with no keys.

### Date shift

`app/agents/date_shift.py` scores **continuous wetness** (mean precip probability), not the binary rainy-day ratio. `rain_ratio()` is retained for diagnostics only. A suggestion is emitted only when wetness exceeds `DATE_SHIFT_RAIN_RATIO` (0.35) **and** an alternate window improves it by `DATE_SHIFT_MIN_IMPROVEMENT` (0.12 absolute) or 25 percent relative.

Diagnostics are attached even when `direction == "none"`, because the UI always renders a weather outlook and only conditionally renders the shift card.

The search window is capped by `extended_len = min(5, stay_len + 2)` in `fetch_forecast`, since the free OpenWeather forecast horizon is about five days. That cap, not the scorer, is what bounds how far a shift can reach.

### Re-plan cycle

`POST /api/trips/{id}/rebuild` does **not** mutate the existing trip. It creates a new trip with a new `trip_id`, `replan_of` set to the old id, and `plan_cycle + 1`, then replays the whole graph from planner. The frontend swaps `tripId`, which restarts polling and resets the chips. Keep re-plan as a fresh graph run rather than a partial patch.

### API and polling

`POST /api/trips/plan` returns `{trip_id}` immediately and runs the graph in a FastAPI `BackgroundTasks`. The UI polls `GET /{id}/status` and `GET /{id}` every 900ms until status is `completed` or `failed`.

### LLM provider

`app/llm/factory.py` and `provider.py` support `heuristic` (default, no key, regex based), `openrouter`, `anthropic`, and `openai`. `parse_constraints` always computes the heuristic result first and returns it if the provider is unset or not ready, and falls back to it on any LLM error. It tries `with_structured_output` first, then raw JSON text parsing. Explicit request fields (city, dates, party size, preferences) always override LLM output.

### MCP tool names

| Service | Tools | Where |
|---|---|---|
| Weather | `get_forecast`, `geocode_city` | external repo, `MCP-Weather-Agent-with-LangChain` |
| Research | `search_pois`, `enrich_poi` | `services/research-mcp/server.py` |
| Dining | `search_restaurants`, `rank_must_try` | `services/dining-mcp/server.py` |

All are reached over streamable HTTP through `langchain_mcp_adapters.MultiServerMCPClient` (`app/mcp/tools.py`). Health checks use `/health`; tool calls use `/mcp`.

The API never holds `OPENWEATHER_API_KEY` or `OPENTRIPMAP_API_KEY`. Those live only on the MCP services.

## Conventions

From `docs/INTEGRITY.md` and `docs/superpowers/specs/2026-07-20-trippi-ai-design.md`:

- Never generate a place name, description, or review. Sourced or absent, no third option.
- Avoid em dashes and decorative dash punctuation in docs and comments; use commas or colons.
- Never hand-edit CHANGELOG or other auto-generated files.
- Report only measured eval numbers, never invented percentages.
- Bug fixes start with an E2E reproduction.
- Feature work merges by PR into `develop`, then `develop` into `main`.

## Known gaps

These are wired in config but not implemented, so do not assume they work:

- `app/memory/postgres.py` and `neo4j_client.py` are never imported. Retrieval runs entirely on the recorded corpus in `fusion.py`, despite `DATABASE_URL` and `NEO4J_URI` settings and the docker-compose services.
- Langfuse is a dependency with three config fields and zero instrumentation.
- `trip_store` is an in-memory dict, so trips do not survive restart and break across multiple workers or instances.
- Research and Dining MCP services are implemented but undeployed, so every environment currently serves the recorded corpus. It covers New York only until `scripts/build_seed_corpus.py` is run with an OpenTripMap key.
- The retrieval eval dataset is three queries over one city. All three strategies score identically (`recall@5 = 0.9167`, hybrid lift `0.0`), so it cannot currently justify the hybrid approach. Widen it before quoting any number.
- Live OpenTripMap results have empty `description` and `neighborhood` (`research_client.py`). Empty neighborhoods silently disable `fusion.graph_expand_poi_indices`, so the live path loses graph expansion. `build_seed_corpus.py` works around this with Wikipedia enrichment; the live MCP path does not yet.
- `npm audit` reports two dev-server-only advisories via esbuild/vite 5. The fix is a breaking upgrade to vite 8, deferred out of the stabilization release.
