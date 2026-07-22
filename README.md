# Trippi-AI

Weather-aware multi-agent travel planner.

LangGraph agents share one trip state to turn a natural language request into a day by day itinerary. The planner adapts indoor vs outdoor activities to the forecast (via a remote Weather MCP), suggests postponing or preponing when too many days look rainy, and picks one local plus one fancy restaurant to try.

**Live UI:** https://trippi-ai-seven.vercel.app  
**Weather MCP (dependency):** https://weather-mcp-oe6z.onrender.com/health  
**Design spec:** [docs/superpowers/specs/2026-07-20-trippi-ai-design.md](docs/superpowers/specs/2026-07-20-trippi-ai-design.md)

## Highlights

- Multi-agent LangGraph graph: planner, researcher, weather, packager, dining, validator
- Parallel researcher + weather fan-out, then weather-aware packaging
- Hybrid retrieval (dense + BM25-style + neighborhood graph) with offline eval script
- Soft date-shift suggestions when rain ratio is high
- Must-try dining: one local, one fancy
- LLM providers: OpenRouter (free), Anthropic Haiku, OpenAI, or heuristic (no key)
- Weather via your [MCP-Weather-Agent-with-LangChain](https://github.com/ankitpatil3003/MCP-Weather-Agent-with-LangChain) `mcp-server` over streamable HTTP

## Architecture

1. Planner parses trip intent.
2. Researcher and Weather run in parallel (hybrid retrieval || remote Weather MCP).
3. Packager builds weather-aware schedules.
4. Dining ranker selects must-try local and fancy spots.
5. Validator schema-checks the trip payload.

## Prerequisites

- Python 3.11+
- Node 20+
- Optional: Docker for Postgres/pgvector and Neo4j
- Deployed Weather MCP URL from [MCP-Weather-Agent-with-LangChain](https://github.com/ankitpatil3003/MCP-Weather-Agent-with-LangChain) (`mcp-server`)

## Quick start (local, stub weather)

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

Open http://localhost:5173. With `MCP_STUB=true` the API does not need a live MCP.

## LLM providers

Set `LLM_PROVIDER` in `backend/.env`:

| Provider | Env | Suggested model | Notes |
|----------|-----|-----------------|-------|
| `heuristic` | none | n/a | No key; rule based parsing (works offline) |
| `openrouter` | `OPENROUTER_API_KEY` | `openrouter/free` | Free router; best zero cost demo path |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-haiku-4-5` | Fast, cheap, strong extraction |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` | Optional fallback |

Optional override: `LLM_MODEL=...` (for example `meta-llama/llama-3.3-70b-instruct:free`).

Example OpenRouter:

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=openrouter/free
```

Example Anthropic:

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-haiku-4-5
```

## Pointing at a real Weather MCP

1. Deploy `mcp-server` to Render first (see weather repo `docs/DEPLOY_RENDER.md`).
2. Set in `backend/.env`:

```env
MCP_STUB=false
MCP_SERVER_URL=https://YOUR_WEATHER_MCP.onrender.com/mcp
```

Example live MCP:

```env
MCP_SERVER_URL=https://weather-mcp-oe6z.onrender.com/mcp
```

Trippi-AI never stores `OPENWEATHER_API_KEY`. Health checks use `/health`; tool calls use `/mcp` with a proper MCP client (not a bare browser GET).

## Tests and eval

```bash
cd backend
pytest -q
python -m evals.retrieval.run_eval
```

Retrieval comparison writes measured metrics to `backend/evals/retrieval/results.json`. Update resume claims from those numbers only.

## Docker compose

```bash
docker compose up --build
```

API on :8080, UI on :5173, Postgres and Neo4j included. Trip planning still uses in-memory seed retrieval in v1; DATABASE_URL/Neo4j are wired for scale-out.

## Cloud deploy order

1. Weather MCP on Render (public `/mcp` and `/health`).
2. Trippi-AI API on Render (`render.yaml`, set `MCP_SERVER_URL`, LLM keys if any, `CORS_ORIGINS`).
3. Frontend on Vercel (`frontend/`, env `VITE_API_URL=https://YOUR_API.onrender.com`).

Free tier cold starts: first MCP call after sleep may take 30 to 60 seconds. The MCP client retries.

See also: [docs/deploy/DEPLOYMENT_STATUS.md](docs/deploy/DEPLOYMENT_STATUS.md) and `scripts/deploy-render-checklist.ps1`.

## Demo script

1. Prompt: `3 days in New York, love views and pizza, prefer museums if it rains`
2. Watch agent chips: planner, researcher, weather, packager, dining, validator.
3. Confirm rainy days skew indoor museums; clear days outdoor views.
4. Confirm Local and Fancy dining cards.
5. If date shift appears, click rebuild and verify new dates.

## Branching

Feature work merges via Pull Request into `develop`, then `develop` into `main` after verification.

## License

See repository `LICENSE`.
