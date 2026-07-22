# Deploy Trippi-AI

## Order

1. Weather MCP (Render) from MCP-Weather-Agent-with-LangChain `mcp-server`
2. Trippi-AI API (Render) using root `render.yaml` / `backend/Dockerfile`
3. Trippi-AI UI (Vercel) from `frontend/` with `VITE_API_URL`

## API env

- `MCP_SERVER_URL` (required in cloud)
- `MCP_STUB=false`
- `OPENAI_API_KEY` (optional; heuristic parser works without it)
- `CORS_ORIGINS` must include your Vercel domain
- `DATE_SHIFT_RAIN_RATIO=0.6`

## Vercel

- Root directory: `frontend`
- Build: `npm run build`
- Output: `dist`
- Env: `VITE_API_URL=https://<api-host>`

## Smoke

```bash
curl -sS https://<api-host>/health
curl -sS -X POST https://<api-host>/api/trips/plan -H "content-type: application/json" -d "{\"prompt\":\"2 days in New York\",\"city\":\"New York\",\"start_date\":\"2026-07-21\",\"end_date\":\"2026-07-22\"}"
```

Poll `GET /api/trips/{id}` until `status` is `completed`.
