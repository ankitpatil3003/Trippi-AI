"""Wikivoyage listing discovery, vendored copy.

The canonical file is `services/research-mcp/wikivoyage.py`. Each MCP service
deploys from its own flat directory with its own Dockerfile, so there is no
shared import path between them. Keep the two copies identical.

Wikivoyage articles carry structured `{{see}}`, `{{do}}` and `{{eat}}` listing
templates with a name, coordinates, a price string and often a Wikidata id. That
is the only open source we have found that knows what a city is actually known
for. OpenTripMap `/radius` cannot answer that question: it returns the nearest
places to a point, capped at 500 rows, which in a large city never reaches the
famous ones. Ranking by its `rate` field does not help either, because hundreds
of entries saturate at the maximum value.

Sourcing note, see docs/INTEGRITY.md. We take from these listings only facts and
identifiers: the name, coordinates, price and Wikidata id. Descriptions come from
Wikipedia, resolved through the Wikidata id when one is present. We do not copy
listing prose, and we do not reproduce the article's ordering as an itinerary.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

WIKIVOYAGE_API = "https://en.wikivoyage.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "TrippiResearchMCP/1.0 (https://github.com/ankitpatil3003/Trippi-AI)"

# Wikivoyage splits large cities into district subarticles and leaves the parent
# article as a table of contents. Cap the fan out so one city stays a bounded
# number of requests.
MAX_DISTRICTS = 12
# Total subarticles fetched per city, across both levels of the walk.
MAX_PAGES = 24
MAX_DEPTH = 2

_LISTING_KINDS = ("see", "do", "eat", "drink", "listing", "marker")


def _balanced_blocks(text: str, kind: str) -> list[str]:
    """Extract `{{kind ...}}` templates, honouring nested braces."""
    blocks: list[str] = []
    for match in re.finditer(rf"\{{\{{\s*{kind}\b", text, re.I):
        start = match.start()
        depth = 0
        index = start
        limit = min(len(text), start + 8000)
        while index < limit:
            pair = text[index : index + 2]
            if pair == "{{":
                depth += 1
                index += 2
                continue
            if pair == "}}":
                depth -= 1
                index += 2
                if depth == 0:
                    blocks.append(text[start:index])
                    break
                continue
            index += 1
    return blocks


def _field(block: str, name: str) -> str:
    """Read one template parameter.

    A plain regex to the next `|` truncates values containing a wiki link, and
    `[[Paris/7th arrondissement#Q243|Eiffel Tower]]` would lose exactly the part
    we want. So scan to the next separator that sits at bracket depth zero.
    """
    match = re.search(rf"\|\s*{name}\s*=", block)
    if not match:
        return ""
    index = match.end()
    depth = 0
    out: list[str] = []
    while index < len(block):
        pair = block[index : index + 2]
        if pair in ("[[", "{{"):
            depth += 1
            out.append(pair)
            index += 2
            continue
        if pair in ("]]", "}}"):
            if depth == 0:
                break
            depth -= 1
            out.append(pair)
            index += 2
            continue
        char = block[index]
        if char == "|" and depth == 0:
            break
        if char == "\n" and depth == 0:
            break
        out.append(char)
        index += 1
    return "".join(out).strip()


def _clean_name(raw: str) -> str:
    """Strip wiki markup from a listing name."""
    text = raw.strip()
    # [[Target#anchor|Label]] or [[Target]]
    text = re.sub(r"\[\[([^\]|]*\|)?([^\]|]+)\]\]", r"\2", text)
    text = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", text)
    text = text.replace("'''", "").replace("''", "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip(" .,-|")
    return text


def _float_or_none(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sections(text: str) -> list[tuple[int, str]]:
    """Offsets of `== Heading ==` markers, used to label each listing."""
    out: list[tuple[int, str]] = []
    for match in re.finditer(r"^=+\s*([^=\n]+?)\s*=+\s*$", text, re.M):
        out.append((match.start(), match.group(1).strip()))
    return out


def _section_for(offset: int, sections: list[tuple[int, str]]) -> str:
    current = ""
    for start, title in sections:
        if start <= offset:
            current = title
        else:
            break
    return current


async def _wikitext(client: httpx.AsyncClient, title: str) -> str:
    resp = await client.get(
        WIKIVOYAGE_API,
        params={
            "action": "parse",
            "page": title,
            "prop": "wikitext",
            "format": "json",
            "formatversion": "2",
            "redirects": "1",
        },
    )
    if resp.status_code >= 400:
        return ""
    payload = resp.json()
    if "error" in payload:
        return ""
    return str((payload.get("parse") or {}).get("wikitext") or "")


# Headings whose listings are not places to visit. Without this, embassy and
# transport listings outrank real sights: New York City's article files "France"
# and "Norway" as consulates, and they parse as perfectly valid listings.
_SKIP_SECTIONS = (
    "embassies", "consulates", "connect", "cope", "stay safe", "stay healthy",
    "get in", "get around", "sleep", "work", "learn", "respect", "talk",
    "understand", "climate", "history", "go next", "buy",
)

_DISTRICT_HEADINGS = ("district", "borough", "region", "neighborhood", "neighbourhood", "area")


def _district_pages(text: str, city: str) -> list[str]:
    """Subarticle titles for a city's districts.

    Two shapes exist. Most cities use a slash prefix, `Paris/7th arrondissement`.
    New York City instead links to standalone borough articles, `Manhattan`, so a
    prefix scan alone finds nothing and the city silently yields no listings.
    """
    found: list[str] = []
    seen = {city.lower()}

    def add(title: str) -> None:
        title = title.strip()
        key = title.lower()
        if not title or key in seen or title.startswith(("File:", "Image:", "Category:")):
            return
        seen.add(key)
        found.append(title)

    for match in re.finditer(rf"\[\[({re.escape(city)}/[^\]|#]+)", text):
        add(match.group(1))

    # Links inside a Districts/Boroughs section, or a {{Regionlist}} template.
    sections = _sections(text)
    for index, (start, title) in enumerate(sections):
        if not any(word in title.lower() for word in _DISTRICT_HEADINGS):
            continue
        end = sections[index + 1][0] if index + 1 < len(sections) else len(text)
        for match in re.finditer(r"\[\[([^\]|#]+)", text[start:end]):
            add(match.group(1))
    for match in re.finditer(r"\|\s*region\d+name\s*=\s*\[\[([^\]|#]+)", text):
        add(match.group(1))

    return found[:MAX_DISTRICTS]


def _parse_listings(text: str, page: str, city: str) -> list[dict[str, Any]]:
    sections = _sections(text)
    rows: list[dict[str, Any]] = []
    if "/" in page:
        neighborhood = page.split("/", 1)[1].strip()
    elif page.lower() != city.lower():
        # A standalone borough article, for example `Manhattan` under New York City.
        neighborhood = page.strip()
    else:
        neighborhood = ""
    for kind in _LISTING_KINDS:
        for block in _balanced_blocks(text, kind):
            name = _clean_name(_field(block, "name"))
            if not name or len(name) < 2:
                continue
            # A district roll-up listing points at another article, not a place.
            if name.lower().startswith(city.lower() + "/"):
                continue
            declared = (_field(block, "type") or kind).lower()
            if declared in ("marker", "listing"):
                declared = "see"
            offset = text.find(block)
            section = _section_for(offset, sections) if offset >= 0 else ""
            if any(skip in section.lower() for skip in _SKIP_SECTIONS):
                continue
            rows.append(
                {
                    "name": name,
                    "kind": declared,
                    "lat": _float_or_none(_field(block, "lat")),
                    "lon": _float_or_none(_field(block, "long")),
                    "wikidata": _field(block, "wikidata"),
                    "price": _clean_name(_field(block, "price"))[:120],
                    "section": section,
                    "neighborhood": neighborhood,
                    "page": page,
                    "source_url": (
                        "https://en.wikivoyage.org/wiki/" + page.replace(" ", "_")
                    ),
                }
            )
    return rows


# Listings for services rather than places. Wikivoyage files scooter hire and
# walking tour operators under `do`, and they rank ahead of real sights on page
# order alone.
_SERVICE_HINTS = (
    "rent",
    "rental",
    "noleggio",
    "hire",
    "tour operator",
    "tours",
    "taxi",
    "transfer",
    "agency",
    "shuttle",
)


def notability(row: dict[str, Any]) -> float:
    """Rank listings so genuine sights beat page order.

    A Wikidata id is the strongest available signal: someone considered the place
    notable enough to model as an entity. Coordinates matter because the packager
    cannot place a block without them.
    """
    score = 0.0
    if row.get("wikidata", "").startswith("Q"):
        score += 3.0
    if row.get("lat") is not None and row.get("lon") is not None:
        score += 1.5
    if row.get("kind") == "see":
        score += 1.0
    if row.get("neighborhood"):
        score += 0.5
    name = row.get("name", "").lower()
    if any(hint in name for hint in _SERVICE_HINTS):
        score -= 2.5
    return score


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = row["wikidata"] or row["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _is_part_of(text: str) -> str:
    """The article's declared parent, from its `{{IsPartOf|...}}` template."""
    match = re.search(r"\{\{\s*ispartof\s*\|\s*([^}|]+)", text, re.I)
    return match.group(1).strip() if match else ""


def diversify(rows: list[dict[str, Any]], limit: int, key: str = "neighborhood") -> list[dict[str, Any]]:
    """Round robin across neighbourhoods, preserving rank inside each.

    Ranking alone concentrates results: every Central Park listing carries a
    Wikidata id and coordinates, so they tie at the top and fill all fourteen New
    York slots with statues and lawns from a single park. A trip planner needs
    spread across the city, not depth in one corner of it.
    """
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(str(row.get(key) or ""), []).append(row)
    out: list[dict[str, Any]] = []
    while len(out) < limit and buckets:
        for bucket_key in list(buckets):
            queue = buckets[bucket_key]
            if not queue:
                del buckets[bucket_key]
                continue
            out.append(queue.pop(0))
            if len(out) >= limit:
                break
    return out


async def _resolve_article(client: httpx.AsyncClient, city: str) -> tuple[str, str]:
    """Find the Wikivoyage article that actually describes the city.

    "New York" is the state, and its article carries no listings at all, so a
    plain lookup silently returns nothing for the largest city in the corpus.
    Try the bare name first, then the disambiguated forms.
    """
    candidates = [city]
    if not city.lower().endswith(" city"):
        candidates.append(f"{city} City")
    for title in candidates:
        text = await _wikitext(client, title)
        if not text:
            continue
        if _parse_listings(text, title, title) or _district_pages(text, title):
            return title, text
    return city, ""


async def city_listings(city: str, pause: float = 0.2) -> list[dict[str, Any]]:
    """All `see`/`do`/`eat` listings for a city, including its district pages.

    Walks two levels because some cities nest twice: New York City lists boroughs,
    and the boroughs list the districts that actually hold the listings. The page
    budget bounds the crawl so one city stays a predictable number of requests.
    """
    rows: list[dict[str, Any]] = []
    visited: set[str] = set()
    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
        title, root = await _resolve_article(client, city)
        if not root:
            return []
        visited.add(title.lower())
        rows.extend(_parse_listings(root, title, title))

        # Only descend into articles that declare themselves part of the city, or
        # of a page we already accepted. A district heading can link anywhere, and
        # without this check New York City reaches Berkeley and files Chez Panisse
        # as a New York restaurant.
        accepted = {title.lower()}
        frontier = [(page, 1) for page in _district_pages(root, title)]
        budget = MAX_PAGES
        while frontier and budget > 0:
            page, depth = frontier.pop(0)
            if page.lower() in visited:
                continue
            visited.add(page.lower())
            # `city` stays the caller's spelling; `title` is the resolved article.
            budget -= 1
            await asyncio.sleep(pause)
            sub = await _wikitext(client, page)
            if not sub:
                continue
            slash_child = page.lower().startswith(title.lower() + "/")
            if not slash_child and _is_part_of(sub).lower() not in accepted:
                continue
            accepted.add(page.lower())
            found = _parse_listings(sub, page, title)
            rows.extend(found)
            # A borough index page carries few listings of its own. Descend once.
            if depth < MAX_DEPTH and len(found) < 5:
                frontier.extend((child, depth + 1) for child in _district_pages(sub, page))
    # Stable sort, so page order still breaks ties within a notability band.
    return _dedupe(sorted(rows, key=notability, reverse=True))


async def _wikidata_titles(ids: list[str]) -> dict[str, str]:
    """Map Wikidata ids to English Wikipedia titles, batched 50 at a time."""
    out: dict[str, str] = {}
    if not ids:
        return out
    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
        for start in range(0, len(ids), 50):
            chunk = ids[start : start + 50]
            resp = await client.get(
                WIKIDATA_API,
                params={
                    "action": "wbgetentities",
                    "ids": "|".join(chunk),
                    "props": "sitelinks",
                    "sitefilter": "enwiki",
                    "format": "json",
                    "formatversion": "2",
                },
            )
            if resp.status_code >= 400:
                continue
            entities = (resp.json() or {}).get("entities") or {}
            for qid, entity in entities.items():
                title = ((entity.get("sitelinks") or {}).get("enwiki") or {}).get("title")
                if title:
                    out[qid] = title
            await asyncio.sleep(0.2)
    return out


async def wikipedia_extracts(titles: list[str]) -> dict[str, dict[str, str]]:
    """Intro extracts for many titles, batched. Keyed by the requested title."""
    out: dict[str, dict[str, str]] = {}
    if not titles:
        return out
    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
        for start in range(0, len(titles), 20):
            chunk = titles[start : start + 20]
            resp = await client.get(
                WIKIPEDIA_API,
                params={
                    "action": "query",
                    "prop": "extracts",
                    "exintro": "1",
                    "explaintext": "1",
                    "titles": "|".join(chunk),
                    "format": "json",
                    "formatversion": "2",
                    "redirects": "1",
                },
            )
            if resp.status_code >= 400:
                continue
            payload = (resp.json() or {}).get("query") or {}
            # `normalized` and `redirects` let us map back to what we asked for.
            alias: dict[str, str] = {}
            for entry in payload.get("normalized", []) or []:
                alias[entry["to"]] = entry["from"]
            for entry in payload.get("redirects", []) or []:
                alias[entry["to"]] = alias.get(entry["from"], entry["from"])
            for page in payload.get("pages", []) or []:
                if page.get("missing") or not page.get("extract"):
                    continue
                title = page["title"]
                requested = alias.get(title, title)
                out[requested] = {
                    "description": re.sub(r"\s+", " ", page["extract"]).strip()[:600],
                    "url": "https://en.wikipedia.org/wiki/" + title.replace(" ", "_"),
                }
            await asyncio.sleep(0.2)
    return out


async def describe(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Resolve descriptions for listings, preferring the Wikidata id when present.

    Returns a map keyed by listing name. Rows without a Wikipedia article get no
    entry, and callers must leave the description empty rather than inventing one.
    """
    qids = [r["wikidata"] for r in rows if r.get("wikidata", "").startswith("Q")]
    qid_titles = await _wikidata_titles(sorted(set(qids)))

    wanted: dict[str, str] = {}
    for row in rows:
        title = qid_titles.get(row.get("wikidata", ""))
        if title:
            wanted[row["name"]] = title
    extracts = await wikipedia_extracts(sorted(set(wanted.values())))

    out: dict[str, dict[str, str]] = {}
    for name, title in wanted.items():
        if title not in extracts:
            continue
        if not _titles_agree(name, title):
            # A wrong Wikidata id in a listing produces a confidently wrong
            # description: the Balto statue came back described as the Balbo
            # Monument. No description is better than someone else's.
            continue
        out[name] = extracts[title]
    return out


_STOPWORDS = {"the", "of", "and", "a", "an", "de", "la", "le", "du", "des", "at", "in", "center", "centre"}


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 2 and t not in _STOPWORDS}


def _titles_agree(listing_name: str, article_title: str) -> bool:
    """Does the resolved Wikipedia article plausibly describe this listing?"""
    left, right = _tokens(listing_name), _tokens(article_title)
    if not left or not right:
        return True
    return bool(left & right)
