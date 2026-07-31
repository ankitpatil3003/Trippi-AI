# Sourcing integrity

Trippi builds its own plans. It does not copy anyone else's.

These rules are product requirements, not style preferences. Code that breaks
them is a defect regardless of how good the output looks.

## 1. Every place must be real and attributable

A POI or restaurant may only appear in a plan if it resolves to a real entity
from an open or licensed source, and carries a source URL. Current sources:

| Source | Used for | Where |
|--------|----------|-------|
| OpenTripMap | POIs, restaurants, geocoding | `services/research-mcp/`, `services/dining-mcp/` |
| OpenStreetMap via Overpass | Restaurants | `services/dining-mcp/dining_client.py` |
| Wikipedia, Wikivoyage | Descriptions and city context | `services/research-mcp/research_client.py` |
| OpenWeather | Forecasts | external Weather MCP service |

Trippi never generates a place name. It has done so before: the fallback used
to build entries by interpolating the requested city, producing strings like
`"Paris Old Town Walk"` and `"Paris Local Kitchen"` and presenting them as
recommendations. That path is deleted, and
`backend/tests/test_integrity_sourcing.py` exists to keep it deleted.

## 2. Opinion sources contribute signals, never content

Reddit, forums, blogs, and similar community sources are legitimate inputs for
**judgment**, and only judgment:

Allowed: sentiment, popularity, "is it worth it" consensus, crowding and timing
hints, pairing suggestions, warnings.

Not allowed: copying a published itinerary or its structure, reproducing
descriptive text beyond a short attributed quote, or presenting another
author's recommendation as Trippi's own.

Store derived aggregates such as scores and counts, not post bodies. Use
official APIs with proper credentials and rate limits, and respect each
platform's terms.

## 3. The plan itself is ours

Sequencing, timing, indoor and outdoor adaptation, the date shift decision, and
dining placement are Trippi's own algorithms operating over sourced facts. This
is the part of the product that is genuinely Trippi's, and it is why copying a
third party itinerary would be both wrong and pointless.

## 4. Unsourced means labeled or absent

Every POI, restaurant, itinerary block, and dining pick carries a `provenance`
field of `live` or `seed`, surfaced in the UI. When nothing can be sourced for a
destination, Trippi says so plainly and returns an empty result. A blank space
is an acceptable answer. A plausible invention is not.

## The recorded corpus

`backend/app/memory/seed_corpus.json` is the degraded-mode fallback. It is a
**recording of real API responses**, not hand-written data, produced by
`scripts/build_seed_corpus.py`. Building it this way means the fallback is real
and attributable by construction rather than by good intentions.

Cities absent from the corpus return nothing. That is the intended behavior.
