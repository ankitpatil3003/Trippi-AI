# Deploy Trippi-AI

## Order

1. **Weather service** (Render) from MCP-Weather-Agent-with-LangChain `mcp-server`
2. **Research service** (Render) from `services/research-mcp`
3. **Dining service** (Render) from `services/dining-mcp`
4. Trippi-AI API (Render) using root `render.yaml` / `backend/Dockerfile`
5. Trippi-AI UI (Vercel) from `frontend/` with `VITE_API_URL`

Steps 2 and 3 are already declared in the root `render.yaml`, so a Blueprint deploy
picks them up without extra configuration. Each service builds from its own
`rootDir` with its own Dockerfile, and `COPY . .` includes the vendored
`wikivoyage.py`.

## API env

- `MCP_SERVER_URL` or `WEATHER_MCP_URL` (Weather service `/mcp`)
- `RESEARCH_MCP_URL` (Research service `/mcp`)
- `DINING_MCP_URL` (Dining service `/mcp`)
- `MCP_STUB=false`
- `RESEARCH_MCP_STUB=false`
- `DINING_MCP_STUB=false`
- `DATE_SHIFT_RAIN_RATIO=0.35`
- `DATE_SHIFT_MIN_IMPROVEMENT=0.12`
- `OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY` (optional; heuristic works)
- `CORS_ORIGINS` must include your Vercel domain

All three stub flags default to **true**. Leaving any of them unset means that
service is never called and the API serves the recorded corpus instead.

## MCP service env

| Service | Secret | Required |
|---------|--------|----------|
| Weather | `OPENWEATHER_API_KEY` | yes |
| Research | `OPENTRIPMAP_API_KEY` | **no** |
| Dining | `OPENTRIPMAP_API_KEY` | **no** |

Research and Dining source from Wikivoyage and Wikipedia, which need no
credentials. An OpenTripMap key only adds fallback POIs and widens the restaurant
candidate pool. Deploy without it if you do not have one.

## Vercel

- Root directory: `frontend`
- Build: `npm run build`
- Output: `dist`
- Env: `VITE_API_URL=https://<api-host>`

## Smoke

Health first. These only prove the processes are up.

```bash
curl -sS https://<research-host>/health
curl -sS https://<dining-host>/health
curl -sS https://<weather-host>/health
curl -sS https://<api-host>/health
```

### Proving the API actually uses the services

A healthy service does not mean the API is reading it. The API falls back to the
recorded corpus on any failure and still returns a complete, real looking plan, so
a green health check plus a good looking itinerary is **not** evidence that the
live path works. That is exactly how a payload unwrapping bug survived: every live
call failed, every response fell back to seed, and nothing looked wrong.

Two checks close that gap.

**Use a city outside the corpus.** The corpus covers New York, Paris, London,
Tokyo, Rome, Barcelona, Amsterdam, Singapore, Dubai and San Francisco. Planning any
of those looks identical whether it came from the services or from the fallback.
Pick something else, for example Lisbon or Prague:

```bash
curl -sS -X POST https://<api-host>/api/trips/plan \
  -H "content-type: application/json" \
  -d '{"prompt":"2 days in Lisbon","city":"Lisbon","start_date":"2026-09-10","end_date":"2026-09-11"}'
```

**Check provenance, not just presence.** Poll `GET /api/trips/{id}` until `status`
is `completed`, then confirm:

- `research_available` is `true` and `dining_available` is `true`
- `pois[].provenance` is `"live"`, not `"seed"`
- `pois[].source_urls` is populated
- `errors[]` does not contain `weak_dining`

If `provenance` reads `seed` for a city that is not in the corpus, the plan is
empty or degraded and the service call failed. Check the API logs for
`Research MCP failed (...)` or `Dining MCP failed (...)`, which name the reason.

Also confirm Weather outlook fields on `date_shift_suggestion`, and `plan_cycle`
after a rebuild.

### Timing

A Research or Dining call walks a city article plus up to 24 district subarticles,
so expect roughly 4 to 8 seconds warm. On Render's free tier add 30 to 60 seconds
for the first call after a sleep. The clients retry, and the graph never blocks on
a failure, but the first plan after idle will feel slow.

Local wetness fixture (stub rainy):

```env
MCP_STUB=true
MCP_STUB_RAINY=true
DATE_SHIFT_RAIN_RATIO=0.35
```
