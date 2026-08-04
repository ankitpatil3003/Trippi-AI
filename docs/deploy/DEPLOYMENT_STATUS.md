# Deployment status (updated for v2 MCP services)

## Live URLs

| Surface | URL / status |
|---------|----------------|
| **Vercel frontend (production)** | **https://trippi-ai-seven.vercel.app** |
| Render Weather MCP | **https://weather-mcp-oe6z.onrender.com/health** |
| Render Research MCP | **pending** deploy from `services/research-mcp` |
| Render Dining MCP | **pending** deploy from `services/dining-mcp` |
| Render Trippi API | set `WEATHER_MCP_URL` / `RESEARCH_MCP_URL` / `DINING_MCP_URL` after MCP deploys |

## Deploy order (v2)

1. Weather service (already live)
2. Research service (`services/research-mcp`, `OPENTRIPMAP_API_KEY`)
3. Dining service (`services/dining-mcp`, same key)
4. Trippi API (`MCP_STUB=false`, `RESEARCH_MCP_STUB=false`, `DINING_MCP_STUB=false`, wetness threshold `0.35`)
5. Vercel `VITE_API_URL`

Smoke: `scripts/deploy-smoke-v2.ps1` and [RENDER_VERCEL.md](./RENDER_VERCEL.md).

## What the live demo actually serves

Research and Dining are undeployed, so the deployed API runs both from the recorded
corpus in `backend/app/memory/seed_corpus.json`. That corpus covers **ten
destinations**: New York, Paris, London, Tokyo, Rome, Barcelona, Amsterdam,
Singapore, Dubai and San Francisco. Any other destination returns no places, the
Research and Dining chips show `skipped`, and the UI states that nothing could be
sourced.

This is intentional. Trippi does not invent places to fill the gap. See
[INTEGRITY.md](../INTEGRITY.md). To widen coverage before the services are deployed,
run `scripts/build_seed_corpus.py`, which needs no API key.

## Notes

- Free tier cold starts: first MCP call after sleep may take 30 to 60 seconds.
- Trippi never stores `OPENWEATHER_API_KEY` or `OPENTRIPMAP_API_KEY` on the API; those live on the MCP services.
- Date-shift uses continuous wetness (`DATE_SHIFT_RAIN_RATIO=0.35`) with Weather outlook always shown in the UI.
