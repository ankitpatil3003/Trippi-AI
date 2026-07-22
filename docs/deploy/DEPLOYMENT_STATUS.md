# Deployment status (2026-07-20)

## Live URLs

| Surface | URL / status |
|---------|----------------|
| **Vercel frontend (production)** | **https://trippi-ai-seven.vercel.app** |
| Render Weather MCP | **not deployed**; needs dashboard (no `RENDER_API_KEY`) |
| Render Trippi API | **not deployed**; needs dashboard (no `RENDER_API_KEY`) |

**Frontend note:** Once the Trippi API is live on Render, set Vercel env **`VITE_API_URL`** to the API base URL (e.g. `https://trippi-ai-api-xxxx.onrender.com`) and redeploy the frontend. Until then the UI may not reach a cloud API.

Also update Render API **`CORS_ORIGINS`** to include `https://trippi-ai-seven.vercel.app` after the API service exists.

---

## Automated attempt result

| Item | Status |
|------|--------|
| `RENDER_API_KEY` (shell env) | **not set** |
| `VERCEL_TOKEN` (shell env) | **not set** |
| `OPENWEATHER_API_KEY` (shell env) | **not set** |
| `mcp-server/.env` exists | **yes** |
| `OPENWEATHER_API_KEY` line in that `.env` | **yes** (value not logged) |
| Render API create/deploy | **blocked** - no API key |
| `npx @render.com/cli` | **impossible** - package 404 on npm |
| `flyctl` / `railway` / `render` CLI | **not installed** on PATH |
| Render local config/session (`~/.render`, AppData) | **none found** |
| Deploy URLs obtained (agent) | Vercel only (manual/dashboard); Render still pending |
| Trippi-AI PR #1 → `develop` | **merged** 2026-07-20 (`https://github.com/ankitpatil3003/Trippi-AI/pull/1`) |
| Trippi-AI `develop` → `main` | **skipped** (per workflow: merge to main only after develop testing) |

CI note: PR #1 backend Ruff failures were fixed in PR #2 (merged to `develop`). Ruff clean; pytest 10 passed.

Helper: `scripts/deploy-render-checklist.ps1` prints exact Render dashboard steps and required env vars.

---

## Deploy order (required)

**MCP weather must be first.** Trippi API needs `MCP_SERVER_URL`. Vercel UI needs the API URL.

1. Weather MCP on Render  
2. Trippi-AI API on Render  
3. Trippi-AI frontend on Vercel: **done** at https://trippi-ai-seven.vercel.app (still needs `VITE_API_URL` when API is live)

---

## Exact clicks: Weather MCP (Render Blueprint)

Repo: `ankitpatil3003/MCP-Weather-Agent-with-LangChain`  
Branch: **`develop`** (PR #17 merged - includes root `render.yaml`)  
Service name in blueprint: `weather-mcp`

1. Open [https://dashboard.render.com](https://dashboard.render.com) and sign in.
2. **New +** → **Blueprint**.
3. Connect GitHub if needed → select **MCP-Weather-Agent-with-LangChain**.
4. Set branch to **`develop`** (not `main` unless you later merge develop→main).
5. Confirm Render detects root **`render.yaml`** (`weather-mcp`, Docker, `rootDir: mcp-server`, health `/mcp`).
6. **Apply** / create the Blueprint.
7. Open the new **weather-mcp** service → **Environment**.
8. Set **`OPENWEATHER_API_KEY`** (paste from local `mcp-server/.env`; do not commit it).
9. **Manual Deploy** → **Deploy latest commit** (or wait for auto-deploy).
10. When live, copy the public URL, e.g. `https://weather-mcp-xxxx.onrender.com`.
11. Smoke: open `https://<weather-host>/mcp` (expect MCP/health response, not 502).

Free tier note: service may sleep; first request can be slow.

---

## Exact clicks: Trippi-AI API (Render)

Repo: `ankitpatil3003/Trippi-AI`  
Branch: **`develop`** (PR #1 merged)  
Blueprint / service: root **`render.yaml`** → `trippi-ai-api`

1. Dashboard → **New +** → **Blueprint** (or **Web Service** if you prefer manual Docker).
2. Select **Trippi-AI**, branch **`develop`**.
3. Confirm **`render.yaml`**: Docker, `rootDir: backend`, health `/health`, plan free.
4. **Apply** / create **trippi-ai-api**.
5. **Environment** - set (required for cloud):
   - `MCP_SERVER_URL` = `https://<weather-host>` (no trailing slash issues; match how the app expects the base URL)
   - `MCP_STUB` = `false` (already defaulted in yaml)
   - `CORS_ORIGINS` = `https://trippi-ai-seven.vercel.app` (add more origins if needed)
   - `OPENAI_API_KEY` = optional
   - `DATE_SHIFT_RAIN_RATIO` = `0.6` (yaml default)
6. Deploy → wait for healthy.
7. Smoke:
   - `GET https://<api-host>/health`
   - Then plan/poll as in `docs/deploy/RENDER_VERCEL.md`
8. On Vercel project → set **`VITE_API_URL`** = `https://<api-host>` → **Redeploy** frontend.

---

## Exact clicks: Trippi-AI UI (Vercel)

**Production URL:** https://trippi-ai-seven.vercel.app

If recreating or adjusting the project:

1. Open [https://vercel.com/new](https://vercel.com/new).
2. **Import** GitHub repo **Trippi-AI**.
3. Branch: **`develop`**.
4. **Root Directory** → **Edit** → `frontend`.
5. Framework: Vite (auto). Build `npm run build`, output `dist`.
6. **Environment Variables**:
   - `VITE_API_URL` = `https://<api-host>` (Trippi Render URL, no path); **set once API is live**.
7. **Deploy**.
8. Copy production URL → go back to Render **trippi-ai-api** → add that origin to **`CORS_ORIGINS`** → redeploy API if needed.
9. Open the Vercel URL and run a short plan smoke in the UI.

CLI alternative (when you have a token): `vercel` / `VERCEL_TOKEN` - not available in this agent session.

---

## Why cloud deploy could not be finished from this session

1. No `RENDER_API_KEY` / `VERCEL_TOKEN` in process, user, or machine environment.
2. Official `npx @render.com/cli` package does not exist on npm (404); no local `render` binary.
3. `flyctl` and `railway` are not on PATH; no local Render CLI config/session dirs.
4. Therefore **Render** services were not created automatically; use the dashboard clicks above (or set `RENDER_API_KEY` and use the REST API).

### To unblock API automation later

```powershell
# User/machine env (restart terminal / Cursor after setting)
[Environment]::SetEnvironmentVariable('RENDER_API_KEY', '<from Render Account → API Keys>', 'User')
[Environment]::SetEnvironmentVariable('VERCEL_TOKEN', '<from Vercel Settings → Tokens>', 'User')
```

Then Render REST: `Authorization: Bearer $env:RENDER_API_KEY` against `https://api.render.com/v1/...`.

Or run: `powershell -File scripts/deploy-render-checklist.ps1`

---

## Next git step (after cloud smoke on develop)

Only after feature testing on **develop**: open a PR **develop → main** for Trippi-AI and merge via GitHub (do not push straight to main).
