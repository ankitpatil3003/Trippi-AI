# Trippi v2 deploy smoke checklist
# Fill URLs after Render deploy, then run each curl.

$ErrorActionPreference = "Stop"

$WeatherHealth = "https://weather-mcp-oe6z.onrender.com/health"
$ResearchHealth = $env:RESEARCH_HEALTH_URL  # e.g. https://trippi-research-mcp.onrender.com/health
$DiningHealth = $env:DINING_HEALTH_URL
$ApiHealth = $env:TRIPPI_API_HEALTH_URL    # e.g. https://trippi-ai-api.onrender.com/health
$ApiBase = $env:TRIPPI_API_URL             # e.g. https://trippi-ai-api.onrender.com

Write-Host "=== Health checks ==="
Invoke-RestMethod $WeatherHealth | ConvertTo-Json -Compress
if ($ResearchHealth) { Invoke-RestMethod $ResearchHealth | ConvertTo-Json -Compress }
if ($DiningHealth) { Invoke-RestMethod $DiningHealth | ConvertTo-Json -Compress }
if ($ApiHealth) { Invoke-RestMethod $ApiHealth | ConvertTo-Json -Compress }

if (-not $ApiBase) {
  Write-Host "Set TRIPPI_API_URL to run plan/rebuild smoke. Local stub path: pytest in backend."
  exit 0
}

Write-Host "=== Plan NYC ==="
$plan = Invoke-RestMethod -Method POST -Uri "$ApiBase/api/trips/plan" -ContentType "application/json" -Body (@{
  prompt = "3 days in New York, love views and pizza"
  city = "New York"
  start_date = "2026-07-21"
  end_date = "2026-07-23"
} | ConvertTo-Json)
$tripId = $plan.trip_id
Write-Host "trip_id=$tripId"

for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Seconds 2
  $trip = Invoke-RestMethod "$ApiBase/api/trips/$tripId"
  if ($trip.status -eq "completed" -or $trip.status -eq "failed") { break }
}
Write-Host "status=$($trip.status) research_available=$($trip.research_available) wetness=$($trip.date_shift_suggestion.wetness) direction=$($trip.date_shift_suggestion.direction)"

if ($trip.date_shift_suggestion.direction -ne "none") {
  Write-Host "=== Rebuild / re-plan cycle ==="
  $rebuild = Invoke-RestMethod -Method POST -Uri "$ApiBase/api/trips/$tripId/rebuild" -ContentType "application/json" -Body (@{
    start = $trip.date_shift_suggestion.suggested_start
    end = $trip.date_shift_suggestion.suggested_end
  } | ConvertTo-Json)
  $newId = $rebuild.trip_id
  for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 2
    $t2 = Invoke-RestMethod "$ApiBase/api/trips/$newId"
    if ($t2.status -eq "completed" -or $t2.status -eq "failed") { break }
  }
  Write-Host "replan status=$($t2.status) plan_cycle=$($t2.plan_cycle) replan_of=$($t2.replan_of)"
}
