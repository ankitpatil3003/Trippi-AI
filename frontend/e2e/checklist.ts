"""
Playwright E2E skeleton.

Run when API + UI are up:
  npx playwright test
Uses MCP stub on the API side. Pixel checks are soft screenshots for manual review.
"""

# Kept as a documented checklist until Playwright is installed in CI secrets environment.
# Happy path:
# 1. Open http://localhost:5173
# 2. Submit default NYC prompt
# 3. Wait for agent chips to reach done
# 4. Assert itinerary days render with weather badges
# 5. Assert dining panel shows Local and Fancy
# 6. With MCP_STUB_RAINY=true and a clearer extended window, assert Date shift card + rebuild

E2E_CHECKLIST = [
    "hero brand Trippi-AI visible",
    "plan form submits without layout overflow on mobile width 390",
    "status chips appear",
    "itinerary days >= 1",
    "dining local + fancy cards",
]
