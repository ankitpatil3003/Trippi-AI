# Trippi-AI

Weather-aware multi-agent travel planner.

LangGraph agents share one trip state to turn a natural language request into a day by day itinerary. Trippi orchestrates your **GitHub MCP services** (Weather, Research, Dining) over streamable HTTP: indoor vs outdoor adapts to the forecast, soft date postpone/prepone when wetness is high, and one local plus one fancy restaurant.

**Live UI:** https://trippi-ai-seven.vercel.app  
**Weather service:** https://weather-mcp-oe6z.onrender.com/health ([MCP-Weather-Agent-with-LangChain](https://github.com/ankitpatil3003/MCP-Weather-Agent-with-LangChain))  
**Design spec:** [docs/superpowers/specs/2026-07-20-trippi-ai-design.md](docs/superpowers/specs/2026-07-20-trippi-ai-design.md)  
**Sourcing integrity:** [docs/INTEGRITY.md](docs/INTEGRITY.md)

## Data sourcing

Trippi never invents a place. Every POI and restaurant resolves to a real entity from
OpenTripMap, OpenStreetMap, or Wikipedia and carries a source URL, tagged `live` or
`seed` in the UI. When a destination cannot be sourced, Trippi says so and returns
nothing rather than filling the gap. See [docs/INTEGRITY.md](docs/INTEGRITY.md).

Current status: the Weather service is deployed and live. Research and Dining are
implemented but **not yet deployed**, so both run from the recorded corpus
(`backend/app/memory/seed_corpus.json`), which currently covers New York only.

## Highlights

- Multi-agent LangGraph: planner, Research service, Weather service, packager, Dining service, validator
- Parallel Research + Weather fan-out, then weather-aware packaging
- Soft date-shift on continuous wetness (not only binary rainy days), with Weather outlook scores in the UI
- Accepting a date shift starts a full **re-plan cycle** from the planner (chips reset)
- Recorded corpus fallback, real places only, when an MCP service is stubbed or down
- LLM providers: OpenRouter (free), Anthropic Haiku, OpenAI, or heuristic (no key)

## Integrated MCP services

| Service | Role | Repo / path |
|---------|------|-------------|
| Weather | Forecast + classification | [MCP-Weather-Agent-with-LangChain](https://github.com/ankitpatil3003/MCP-Weather-Agent-with-LangChain) `mcp-server` |
| Research | Live POIs (OpenTripMap + Wikipedia) | `services/research-mcp/` |
| Dining | Live restaurants (OTM + Overpass) | `services/dining-mcp/` |

Trippi LangGraph nodes are thin MCP clients. Seed data is used only as a degraded fallback.

## Architecture

1. Planner parses trip intent.
2. Research service and Weather service run in parallel.
3. Date-shift scorer attaches outlook diagnostics (and a soft suggestion when a drier window exists).
4. Packager builds weather-aware schedules.
5. Dining service ranks must-try local and fancy spots.
6. Validator schema-checks the trip payload.
7. On accept date shift: new trip with `plan_cycle` + 1, full graph replay from planner.

## Prerequisites

- Python 3.11+
- Node 20+
- Optional: Docker for Postgres/pgvector and Neo4j
- Free [OpenTripMap](https://opentripmap.io/) key for Research and Dining services
- Deployed Weather MCP URL from your weather repo

## Quick start (local, stub MCPs)

```bash
# Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # or cp
uvicorn app.main:app --reload --port 8080

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. With `MCP_STUB=true` / `RESEARCH_MCP_STUB=true` / `DINING_MCP_STUB=true` the API does not need live MCP URLs.

If port 8080 is already taken locally, for example by Apache, run the API elsewhere
and point the dev proxy at it:

```bash
uvicorn app.main:app --reload --port 8081        # backend
VITE_PROXY_TARGET=http://127.0.0.1:8081 npm run dev   # frontend
```

## Rebuilding the recorded corpus

The fallback corpus is a recording of real API responses, not hand written data.

```bash
export OPENTRIPMAP_API_KEY=...       # or services/research-mcp/.env
python scripts/build_seed_corpus.py                  # all destinations
python scripts/build_seed_corpus.py --cities "Paris" # one destination
```

A destination that fails to fetch is skipped, never filled in with a placeholder.

## LLM providers

Set `LLM_PROVIDER` in `backend/.env`:

| Provider | Env | Suggested model | Notes |
|----------|-----|-----------------|-------|
| `heuristic` | none | n/a | No key; rule based parsing (works offline) |
| `openrouter` | `OPENROUTER_API_KEY` | `openrouter/free` | Free router; best zero cost demo path |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-haiku-4-5` | Fast, cheap, strong extraction |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` | Optional fallback |

## Pointing at live MCP services

```env
MCP_STUB=false
RESEARCH_MCP_STUB=false
DINING_MCP_STUB=false
MCP_SERVER_URL=https://weather-mcp-oe6z.onrender.com/mcp
# or WEATHER_MCP_URL=...
RESEARCH_MCP_URL=https://YOUR_RESEARCH_MCP.onrender.com/mcp
DINING_MCP_URL=https://YOUR_DINING_MCP.onrender.com/mcp
DATE_SHIFT_RAIN_RATIO=0.35
DATE_SHIFT_MIN_IMPROVEMENT=0.12
```

Trippi-AI never stores `OPENWEATHER_API_KEY` or `OPENTRIPMAP_API_KEY` on the API; those live on the MCP services. Health checks use `/health`; tool calls use `/mcp` with a proper MCP client.

## Tests and eval

```bash
cd backend
pytest -q                          # hermetic, no network calls
python -m evals.retrieval.run_eval # deterministic, safe to diff

cd ../frontend
npm run lint
npm run test:e2e                   # needs the API running with MCP_STUB=true
```

Retrieval eval numbers are measured, not estimated. On the current three query
NYC dataset, dense, dense+BM25, and full hybrid all score `recall@5 = 0.9167`,
so the measured hybrid lift is `0.0`. The dataset is too small to separate the
strategies; widening it is tracked for the next release.

## Cloud deploy order

1. Weather MCP on Render (public `/mcp` and `/health`).
2. Research MCP + Dining MCP on Render (`services/*/`, set `OPENTRIPMAP_API_KEY`).
3. Trippi-AI API on Render (`render.yaml`, set MCP URLs, LLM keys if any, `CORS_ORIGINS`).
4. Frontend on Vercel (`frontend/`, env `VITE_API_URL`).

Free tier cold starts: first MCP call after sleep may take 30 to 60 seconds. Clients retry.

See: [docs/deploy/RENDER_VERCEL.md](docs/deploy/RENDER_VERCEL.md) and [docs/deploy/DEPLOYMENT_STATUS.md](docs/deploy/DEPLOYMENT_STATUS.md).

## Demo script

1. Prompt: `3 days in New York, love views and pizza, prefer museums if it rains`
2. Watch service chips: Planner, Research service, Weather service, Packager, Dining service, Validator.
3. Confirm Weather outlook scores even when direction is `none`.
4. Confirm rainy days skew indoor; clear days outdoor.
5. Confirm Local and Fancy dining cards.
6. If date shift appears, accept and verify **Re-plan cycle 2** with chips replaying.

## Branching

Feature work merges via Pull Request into `develop`, then `develop` into `main` after verification.

## License

See repository `LICENSE`.
