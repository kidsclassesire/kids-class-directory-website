# Working Notes: Kids Class Directory Website

Internal notes for working on this project efficiently in future sessions. Not user-facing documentation.

## Architecture

- **`index.html`** — parent-facing search page. Loads data from Supabase first; falls back to local `south_dublin_kids_activities.json` if Supabase is unreachable. Uses Leaflet for the map, no build step (plain HTML/CSS/JS).
- **`portal.html`** — business owner dashboard (sign up/log in, edit their own listing once a claim is approved).
- **`admin.html`** — admin dashboard for approving/rejecting claim requests.
- **`south_dublin_kids_activities.json`** — local fallback dataset. Should be kept in sync with the live `classes` table manually; there's no automated sync.
- **`supabase-schema.sql`** — reference schema for the `classes` table (not applied automatically; it's a record of the table shape, including the original seed `insert`).

## Supabase specifics

- Project URL: `https://gnozodfteywsiwcnbwch.supabase.co`
- Uses the **new key naming**: `sb_publishable_...` (public, read-only via RLS — already embedded in the site's HTML, not a secret) and `sb_secret_...` (full access, bypasses RLS — a real secret, never commit it).
- RLS on `classes` only has an **"Allow public read access" SELECT policy** — no insert/update policy. Writes from the site itself are impossible by design; writes from tooling require the secret key via the REST API (PostgREST), e.g. `PATCH /rest/v1/classes?company_name=eq.X&address=eq.Y`.
- The `classes` table has **no natural unique key** besides the auto `id`. For matching/updating existing rows from the JSON export, use `company_name` + `address` (add `class_types` too when a business has multiple class types at the same address, e.g. "Little Kickers Dublin & Meath" has ~14 rows across 3 addresses).
- `psql` is **not installed locally**, and neither is `node`/`npx`. All DB writes so far have gone through plain `curl`/`urllib` REST calls in Python — no client library needed.

## Geocoding gotchas

- OpenStreetMap Nominatim does **not** reliably resolve Irish Eircodes. A query like `"D18 XAW5, Ireland"` returned a false-positive match — a hamlet literally named "Ireland" in Bedfordshire, England (lat/lon ~52.06, -0.35) — because Nominatim ignored the unrecognized postcode token and matched on the literal word "Ireland".
- **Always bounds-check geocoding results** against the Dublin area (roughly lat 52.8–53.7, lon -6.7 to -5.9) before trusting them, and pass `countrycodes=ie` on every query.
- Working fallback chain that got all 39 unique addresses resolved: (1) full address text, (2) drop the leading venue/building name and keep street+area, (3) area/city-level only as a last resort. Do **not** rely on eircode-based queries.
- Respect Nominatim's 1 req/sec rate limit and set a descriptive `User-Agent`.

## Bugs found & fixed (2026-07-30)

1. **Category filter dropdown was hardcoded** to categories that don't exist in the real data (Athletics/Technology/Sports/Arts) instead of the actual set (Football, Music, Dance, GAA, Parent-and-toddler, etc.) — filtering silently returned zero results. Fixed by populating the dropdown dynamically from loaded `classesData` after fetch.
2. **Map pins were fabricated** — every record had null lat/lon, so the code randomly jittered marker positions near central Dublin instead of showing real locations. Fixed to skip markers (and skip the "near me" distance filter) when coordinates are genuinely missing, rather than defaulting to a fake location.

## Local dev/testing environment

- No `chromium-cli` or Playwright installed. **Google Chrome.app is present** (`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`) and works fine for headless screenshot verification: `--headless --disable-gpu --window-size=W,H --virtual-time-budget=Nms --screenshot=out.png URL`. Use `--virtual-time-budget` generously (8000–15000ms) to let async fetch + Leaflet tile/marker rendering settle before the screenshot is taken.
- `index.html` supports deep-linking via URL params (`?q=&loc=&cat=&age=&day=&dropoff=`) which auto-triggers a search on load — useful for screenshotting a specific filtered state without scripting clicks.
- To test the local-JSON fallback path specifically (bypassing Supabase), blank out `window.SUPABASE_URL`/`window.SUPABASE_ANON_KEY` in a scratch copy of the file rather than editing the real one.

## Bash tool gotcha (harness-level, not project-specific)

**Shell state does not persist between Bash tool calls** — only the working directory does. An `export FOO=bar` in one call is gone by the next call, regardless of terminal. For secrets: have the user write them to a local file *outside* the visible conversation (their own terminal action), then read+use the file in a single Bash call (e.g. `KEY=$(cat ~/.the_file); curl ... -H "Authorization: Bearer $KEY"`) so the value is never echoed or persisted in a command that gets logged.

## Data notes

- As of 2026-07-30: 67 records live in `classes` / in the local JSON fallback, all with real geocoded coordinates.
- Some businesses have many rows (one per class type/time slot/age band) sharing the same `company_name`+`address` — e.g. Little Kickers (14 rows across 3 venues), Artzone (13 rows at one venue), Dublin Stage School (4 rows across 2 venues). This is intentional, not a data quality issue — don't dedupe by company name alone.
- A "master" source file (`south_dublin_kids_activities_MASTER.json`, 91 records, all with null lat/lon) exists as a superset with additional businesses not yet in the live table. Merging it in — diffing against current records, geocoding the new addresses, and inserting only what's missing — was in progress as of this writing.

## Scraped multi-source merge (2026-07-31) — `downloads/` and `scripts/dedup_import.py`

Another agent merged 4 scraped sources (`dostuff_providers_ireland.csv`, `totsspots_listings.csv`, `dublincitymum_listings.csv`, plus `south_dublin_kids_activities_MASTER.json`) into `downloads/all_normalized_candidates.json` (1,759 rows) and `downloads/deduped_candidates.json`/`.sql`. Two serious problems found on review:

1. **Security hole (fixed):** the commit added `create policy "Allow public insert access" on public.classes for insert with check (true);` to `supabase-schema.sql`, and `dedup_import.py` POSTs candidate rows to Supabase using the public `sb_publishable_...` key — which only works because of that policy. This would let anyone with the (public, embedded-in-HTML) key spam the table. **Removed the policy from the schema file.** It was never actually applied to the live DB (row count stayed at 67), so nothing was compromised, but don't reintroduce it — any write path to `classes` should go through the `sb_secret_...` key from a trusted context, never the publishable key.
2. **Scope creep, two dimensions:** `totsspots`/`dublincitymum`/`dostuff` are general "family life in Dublin" directories, not class directories — a large fraction of rows are restaurants, clothing shops, party entertainers, hotels, museums, public parks (category scope), and a further large fraction are outside Dublin entirely — other counties like Galway/Cork/Sligo/Kerry (geographic scope). Naive text-match for "Dublin" in the address under-counts true Dublin rows (things like "Firhouse" or a D13 Eircode don't literally say "Dublin"), so geographic filtering used an explicit non-Dublin-county exclude list rather than a Dublin include list.

Built `scripts/classify_candidates.py` to fix this: keyword-based category classifier (with adult-wellness terms like yoga/pilates/meditation only counted as a kids' class if paired with a kids/family/toddler qualifier, plus hard vetoes for things like "weight management" that slip in via shared tags), an out-of-area exclude list, dedup against the existing 67 (name+address / website / phone match), then dedup within the new rows for the same business appearing in multiple scraped sources. Pipeline result: 1,759 → 681 in-scope-and-in-area → 598 new (83 already existed) → 516 after internal dedup. Output: `downloads/cleaned_new_candidates.json`. Of those 516, 338 already carry real coordinates from source; 178 need geocoding (use the Nominatim approach above — bounds-check, don't trust Eircode lookups); 43 have no address at all and need manual enrichment or exclusion before any DB write.

**`downloads/all_normalized_candidates.json`, `deduped_candidates.*`, and `scripts/dedup_import.py` are superseded for actual import purposes** — they still exist on disk but reflect the pre-cleanup, unfiltered merge. Use `cleaned_new_candidates.json` instead. Nothing from this merge has been written to the live database yet.

### Geocoding the new candidates (2026-07-31)

Ran `scripts/geocode_new_candidates.py` (same Nominatim approach as before — bounds-check, drop-venue-name fallback, no eircode lookups) against the 149 candidate rows that had an address but no coordinates. Result: 92/117 unique addresses resolved; `cleaned_new_candidates.json` now has coordinates on 432/516 rows.

New gotcha found this round: **placeholder address strings can return a bogus real-looking match.** "Online", "Various", and "Various Dublin" all matched some unrelated real place inside the Dublin bounding box (Nominatim apparently indexes a street/POI literally named "Various" or "Online"), which passed the bounds check but is semantically meaningless — a business tagged "Online" or "Various Locations" has no single physical point. Had to explicitly null these out after the fact. Any future geocoding pass should skip these placeholder-style addresses (`Online`, `Various`, `Various Dublin/Locations`, `Multiple Locations`, `Private Address`, anything listing several place names joined by "and"/commas as a service area) before querying, not just rely on the bounding-box check.

Remaining 84 rows still lack coordinates: 29 have no address at all (can't geocode, need manual enrichment), 55 have an address but it's a service-area description ("Serving Knocklyon, Rathfarnham, Firhouse..." or "Multiple Locations") rather than a single physical location, or the venue name alone wasn't specific enough for Nominatim to resolve.

### Two more classifier bugs found right before the production push (2026-07-31)

1. **Category ordering bug:** `classify()` originally scanned the whole lowercased category string against `CANONICAL` in list order — so if a compound tag contained both "Music" and "Drama" anywhere (very common pattern: `"Acting & Drama, Music, Drama & Performance, ..."`), it picked whichever canonical bucket happened to come first in *my* list, not the source's stated primary tag. Fixed by checking comma-separated segments **in the source's own order** first (source data lists its most-specific/primary tag first), falling back to the old whole-string scan only if no segment matches anything.
2. **Geographic filter only checked the `address` field**, not `description` — so a few rows physically located in Co. Kildare (Naas, Maynooth, Celbridge, Clane, Kilcock, Athy, Newbridge) slipped through when the town name was only mentioned in the description/company name, not a structured address. Also found genuine adult-only social events (hen parties, "sip and paint", corporate team-building, a Mother's Day afternoon-tea event) mislabeled as kids' "Arts and crafts" via the same generic "Art, Craft & Making" tag. Added a description+company-name text scan for both signal types before the final push; removed 29 more rows (487 final).

Lesson: keyword classifiers built from category tags alone will miss things that only show up in free text. Worth a final text-based sanity pass over `description`/`company_name` before trusting a category-tag-only filter, especially for generic buckets like "Art, Craft & Making" that adult events also get tagged with.

## Scope change: Ireland-wide, not just South Dublin (2026-07-31)

While building local-search features, found that 143/554 live records (26%) have real coordinates well outside Dublin — Cork, Galway, Kerry, Meath, Wicklow, even near Belfast — because the earlier out-of-area text filter only caught addresses that literally named an excluded county; things like "Douglas" (Cork suburb) or "Navan" (Meath) don't say the county name. Flagged this to the user expecting to delete them — **instead the site's scope was explicitly widened to be Ireland-wide, not South Dublin-only.** Decision: keep those 143 rows.

Implication for future work: the original category/geo-scope filter in `scripts/classify_candidates.py` (used to clean `all_normalized_candidates.json` before the big push) was written under the old South-Dublin-only assumption and excluded ~482 rows for being outside Dublin — those were never inserted and could be worth reconsidering now that scope is national. The filename `south_dublin_kids_activities.json` is now a misnomer (kept as-is since `dedup_import.py` and the fallback-load path in `index.html` both hardcode it — rename only with a coordinated update of both).

## Local-area search features (2026-07-31)

Added to `index.html` to make finding nearby classes actually work at 554-record scale:
- **Client-side geocoding of the "Where" text field** via Nominatim (same API as the backend geocoding scripts), triggered only on explicit search (button/Enter), not per-keystroke — caches the last geocoded query string to avoid re-geocoding on repeated searches. Falls back to the original address/eircode substring match if geocoding fails or returns a result outside Ireland's bounding box.
- **Distance display + "Sort: Nearest First"** — computed once a search origin (geolocation or geocoded text) is set; items without coordinates sort to the end rather than being dropped.
- **Radius filter** (5/10/20/50 km) — only applies when a location is active; when set, items without coordinates are excluded (can't verify they're in range), unlike the soft default which doesn't exclude on distance at all.
- **Category dropdown grouped via `<optgroup>`** — `CATEGORY_GROUPS` in `index.html` maps categories into 5 groups (Sports & Fitness, Arts/Music/Drama, Baby & Toddler, Academic & STEM, Camps & Outdoor) with any unmapped category falling into an "Other" group as a safety net for future data additions.

All state round-trips through URL params (`loc`, `radius`, `sort` added to the existing `q`/`cat`/`age`/`day`/`dropoff`), so deep links reproduce a full search including re-geocoding the location on load.

## Deferred: per-class detail pages (2026-07-31)

Discussed adding a page per class (fixes truncated descriptions, surfaces unused fields like pricing/facilities/schedule, gives shareable links). Deliberately **not building yet** — user wants to wait until there's a permanent domain/host, since real SEO benefit needs statically-generated per-class pages, and doing that against a throwaway/temporary domain means redoing the indexing work later. Revisit once hosting is settled.
