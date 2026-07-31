# Dining MCP

Live restaurant search for Trippi-AI via OpenTripMap + OpenStreetMap Overpass, with local/fancy ranking.

## Tools

- `search_restaurants(city, cuisine_prefs, limit)`
- `rank_must_try(city, candidates?)`

## Local

```bash
cd services/dining-mcp
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# set OPENTRIPMAP_API_KEY from https://opentripmap.io/
python server.py
```

Health: `http://127.0.0.1:8011/health`  
MCP: `http://127.0.0.1:8011/mcp`

## Render

Deploy this folder as a Docker web service. Set `OPENTRIPMAP_API_KEY`. Point Trippi API:

```env
DINING_MCP_URL=https://YOUR_SERVICE.onrender.com/mcp
DINING_MCP_STUB=false
```
