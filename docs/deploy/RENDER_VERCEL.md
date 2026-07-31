# Deploy Trippi-AI

## Order

1. **Weather service** (Render) from MCP-Weather-Agent-with-LangChain `mcp-server`
2. **Research service** (Render) from `services/research-mcp` (set `OPENTRIPMAP_API_KEY`)
3. **Dining service** (Render) from `services/dining-mcp` (same OpenTripMap key)
4. Trippi-AI API (Render) using root `render.yaml` / `backend/Dockerfile`
5. Trippi-AI UI (Vercel) from `frontend/` with `VITE_API_URL`

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

## MCP service env

| Service | Secret |
|---------|--------|
| Weather | `OPENWEATHER_API_KEY` |
| Research | `OPENTRIPMAP_API_KEY` |
| Dining | `OPENTRIPMAP_API_KEY` |

## Vercel

- Root directory: `frontend`
- Build: `npm run build`
- Output: `dist`
- Env: `VITE_API_URL=https://<api-host>`

## Smoke

```bash
curl -sS https://<research-host>/health
curl -sS https://<dining-host>/health
curl -sS https://<weather-host>/health
curl -sS https://<api-host>/health

# Plan
curl -sS -X POST https://<api-host>/api/trips/plan -H "content-type: application/json" -d "{\"prompt\":\"2 days in New York\",\"city\":\"New York\",\"start_date\":\"2026-07-21\",\"end_date\":\"2026-07-22\"}"
```

Poll `GET /api/trips/{id}` until `status` is `completed`. Check `research_available`, `pois[].source_urls`, Weather outlook fields on `date_shift_suggestion`, and `plan_cycle` after rebuild.

Local wetness fixture (stub rainy):

```env
MCP_STUB=true
MCP_STUB_RAINY=true
DATE_SHIFT_RAIN_RATIO=0.35
```
