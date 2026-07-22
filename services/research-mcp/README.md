# Research MCP

Live POI search for Trippi-AI via OpenTripMap + Wikipedia enrichment.

## Tools

- `search_pois(city, preferences, indoor_outdoor, limit)`
- `enrich_poi(name, city)`

## Local

```bash
cd services/research-mcp
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# set OPENTRIPMAP_API_KEY from https://opentripmap.io/
python server.py
```

Health: `http://127.0.0.1:8010/health`  
MCP: `http://127.0.0.1:8010/mcp`

## Render

Deploy this folder as a Docker web service. Set `OPENTRIPMAP_API_KEY`. Point Trippi API:

```env
RESEARCH_MCP_URL=https://YOUR_SERVICE.onrender.com/mcp
RESEARCH_MCP_STUB=false
```
