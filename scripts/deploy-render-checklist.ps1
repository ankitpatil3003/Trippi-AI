<#
.SYNOPSIS
  Prints exact Render dashboard deploy steps and required env vars for Trippi-AI.

.DESCRIPTION
  Use when RENDER_API_KEY is unavailable and CLIs (render/flyctl/railway) are not installed.
  Does not deploy; checklist only.

.EXAMPLE
  powershell -File scripts/deploy-render-checklist.ps1
#>

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "=== Trippi-AI / Weather MCP: Render deploy checklist ===" -ForegroundColor Cyan
Write-Host "Generated for local use when API automation is blocked (no RENDER_API_KEY)."
Write-Host ""

Write-Host "Prerequisites" -ForegroundColor Yellow
Write-Host "  - GitHub: ankitpatil3003/MCP-Weather-Agent-with-LangChain (branch develop)"
Write-Host "  - GitHub: ankitpatil3003/Trippi-AI (branch develop)"
Write-Host "  - Dashboard: https://dashboard.render.com"
Write-Host "  - Optional automation later: set User env RENDER_API_KEY from Render Account → API Keys"
Write-Host ""

Write-Host "Order (required)" -ForegroundColor Yellow
Write-Host "  1) Weather MCP  2) Trippi API  3) Vercel VITE_API_URL + CORS"
Write-Host ""

Write-Host "--- Step 1: Weather MCP (Blueprint) ---" -ForegroundColor Green
Write-Host "  1. New + → Blueprint → MCP-Weather-Agent-with-LangChain → branch develop"
Write-Host "  2. Confirm root render.yaml (service weather-mcp, Docker, rootDir mcp-server)"
Write-Host "  3. Apply / create"
Write-Host "  4. Environment → set:"
Write-Host "       OPENWEATHER_API_KEY   (required; from local mcp-server/.env; do not commit)"
Write-Host "  5. Deploy latest → copy URL e.g. https://weather-mcp-xxxx.onrender.com"
Write-Host "  6. Smoke: GET https://<weather-host>/mcp"
Write-Host ""

Write-Host "--- Step 2: Trippi-AI API (Blueprint) ---" -ForegroundColor Green
Write-Host "  1. New + → Blueprint → Trippi-AI → branch develop"
Write-Host "  2. Confirm root render.yaml (service trippi-ai-api, Docker, rootDir backend, health /health)"
Write-Host "  3. Apply / create"
Write-Host "  4. Environment → set:"
Write-Host "       MCP_SERVER_URL          = https://<weather-host>   (required)"
Write-Host "       MCP_STUB                = false"
Write-Host "       CORS_ORIGINS            = https://trippi-ai-seven.vercel.app"
Write-Host "       OPENAI_API_KEY          = <optional>"
Write-Host "       DATE_SHIFT_RAIN_RATIO   = 0.6"
Write-Host "  5. Deploy → Smoke: GET https://<api-host>/health"
Write-Host ""

Write-Host "--- Step 3: Wire Vercel frontend ---" -ForegroundColor Green
Write-Host "  Frontend already live: https://trippi-ai-seven.vercel.app"
Write-Host "  1. Vercel project → Settings → Environment Variables:"
Write-Host "       VITE_API_URL = https://<api-host>   (no trailing path)"
Write-Host "  2. Redeploy frontend (Vite bakes VITE_* at build time)"
Write-Host "  3. Confirm Render CORS_ORIGINS includes https://trippi-ai-seven.vercel.app"
Write-Host ""

Write-Host "Required env vars (summary)" -ForegroundColor Yellow
Write-Host "  weather-mcp:     OPENWEATHER_API_KEY"
Write-Host "  trippi-ai-api:   MCP_SERVER_URL, CORS_ORIGINS [, OPENAI_API_KEY, MCP_STUB, DATE_SHIFT_RAIN_RATIO]"
Write-Host "  Vercel frontend: VITE_API_URL (after API is live)"
Write-Host ""

Write-Host "Local CLI status (this machine)" -ForegroundColor Yellow
foreach ($cmd in @("render", "flyctl", "railway")) {
  $found = Get-Command $cmd -ErrorAction SilentlyContinue
  if ($found) {
    Write-Host ("  {0}: {1}" -f $cmd, $found.Source)
  } else {
    Write-Host ("  {0}: not on PATH" -f $cmd)
  }
}
if ($env:RENDER_API_KEY) {
  Write-Host "  RENDER_API_KEY: set (value not printed)"
} else {
  Write-Host "  RENDER_API_KEY: not set; use dashboard or set User env and restart shell"
}
Write-Host ""
Write-Host "Docs: docs/deploy/DEPLOYMENT_STATUS.md , docs/deploy/RENDER_VERCEL.md"
Write-Host ""
