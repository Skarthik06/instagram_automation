# Agent 15 — Location Intelligence & Asset Acquisition

> Inherits [../AGENTS.md](../AGENTS.md). Added to enrich carousels with factual,
> real-world context WITHOUT fabricating property visuals (Spec §15, §16, §18).

**Mission** — From the verified location, acquire factual context assets — a real
map, nearby hotspots (metro/malls/hospitals/schools/parks), and optional licensed
contextual imagery — to make posts richer and widen reach, while never
misrepresenting the property.

**Stage & boundary** — Extraction/enrichment (deterministic + open geodata APIs).
Feeds the Marketing/Carousel agents. No property fact invention.

**Inputs** — Validated `location` (locality, city) + brochure `connectivity` list.

**Outputs** — `location_intelligence`:
`{geocode:{lat,lon,source}, hotspots:[{name,category,distance_km,distance_kind:
CALCULATED_DISTANCE,source:"OpenStreetMap"}], map_asset:{storage_ref,cdn_url,
asset_type:"context_map",attribution}, context_images?:[...]}`.

**Tools/models allowed**
- **Nominatim** (geocoding), **Overpass** (nearby POIs), **OSM tiles** for a real
  static map — free, no key, with a proper User-Agent + on-disk caching.
- Optional licensed stock imagery **only behind a configured API key**, used ONLY on
  clearly-contextual slides, with attribution. Off by default.
- Deterministic image composition (Pillow). No LLM.

**MUST**
- Label every acquired asset as **context** (`context_map` / `context_photo`), never
  as the property's own building/interior/floor plan (Spec §15).
- Mark geodata distances as **CALCULATED_DISTANCE**, distinct from the brochure's
  **SOURCE_DOCUMENT_DISTANCE** (Spec §18) — never present calculated as source-stated.
- Attribute sources ("© OpenStreetMap contributors" / stock credit).
- Only send a public **place name** (locality/city) to geo APIs — never PII
  (names, phones, addresses) (§3). Only fixed, reputable endpoints; never a URL
  taken from the document.
- Cache aggressively (tiles, geocode, POIs); degrade gracefully if offline.

**MUST NOT**
- Present a fetched/stock/map image as the actual property or its amenities.
- Fabricate a hotspot, distance, or coordinate; if geodata is unavailable, omit it.
- Exceed free-tier usage policies (rate-limit + cache); for commercial scale, swap
  to a keyed tile/geocode provider (config).

**Escalation** — Geocode ambiguous/low-confidence → skip map, flag for review.

**Cost budget** — Free geodata + local compose; optional keyed stock behind budget.

**Monitored metrics** — geocode success rate, hotspots found, map render time, cache
hit rate, external calls/property.

**Failure modes** — offline/blocked APIs, wrong geocode, sparse POIs → degrade to
brochure-only assets; never block the pipeline.
