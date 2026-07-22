<#
.SYNOPSIS
  Prints exact Render dashboard deploy steps and required env vars for Trippi-AI v2.

.DESCRIPTION
  Use when RENDER_API_KEY is unavailable. Does not deploy; checklist only.

.EXAMPLE
  powershell -File scripts/deploy-render-checklist.ps1
#>

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "=== Trippi-AI v2: Render deploy checklist (MCP services) ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "Order (required)" -ForegroundColor Yellow
Write-Host "  1) Weather service  2) Research service  3) Dining service  4) Trippi API  5) Vercel"
Write-Host ""

Write-Host "--- Step 1: Weather service (already live example) ---" -ForegroundColor Green
Write-Host "  https://weather-mcp-oe6z.onrender.com/health"
Write-Host "  Env on that service: OPENWEATHER_API_KEY"
Write-Host ""

Write-Host "--- Step 2: Research service ---" -ForegroundColor Green
Write-Host "  1. New + → Web Service → Trippi-AI → rootDir services/research-mcp → Docker"
Write-Host "  2. Environment → OPENTRIPMAP_API_KEY (https://opentripmap.io/)"
Write-Host "  3. Smoke: GET https://<research-host>/health"
Write-Host "  4. MCP URL: https://<research-host>/mcp"
Write-Host ""

Write-Host "--- Step 3: Dining service ---" -ForegroundColor Green
Write-Host "  Same as Research but rootDir services/dining-mcp"
Write-Host "  Same OPENTRIPMAP_API_KEY"
Write-Host ""

Write-Host "--- Step 4: Trippi-AI API ---" -ForegroundColor Green
Write-Host "  Environment:"
Write-Host "       MCP_SERVER_URL / WEATHER_MCP_URL = https://<weather-host>/mcp"
Write-Host "       RESEARCH_MCP_URL                 = https://<research-host>/mcp"
Write-Host "       DINING_MCP_URL                   = https://<dining-host>/mcp"
Write-Host "       MCP_STUB                         = false"
Write-Host "       RESEARCH_MCP_STUB                = false"
Write-Host "       DINING_MCP_STUB                  = false"
Write-Host "       DATE_SHIFT_RAIN_RATIO            = 0.35"
Write-Host "       DATE_SHIFT_MIN_IMPROVEMENT       = 0.12"
Write-Host "       CORS_ORIGINS                     = https://trippi-ai-seven.vercel.app"
Write-Host "       OPENROUTER_API_KEY / ANTHROPIC   = optional"
Write-Host ""

Write-Host "--- Step 5: Vercel ---" -ForegroundColor Green
Write-Host "  VITE_API_URL = https://<api-host>"
Write-Host ""

Write-Host "Smoke script: scripts/deploy-smoke-v2.ps1" -ForegroundColor Cyan
Write-Host "Local wet stub: MCP_STUB=true MCP_STUB_RAINY=true DATE_SHIFT_RAIN_RATIO=0.35"
Write-Host ""
