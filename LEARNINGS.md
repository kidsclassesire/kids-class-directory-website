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

## Mobile layout fixes + marker clustering (2026-07-31)

Fixed three real mobile UX problems, found by actually screenshotting a 390px viewport rather than just reviewing CSS:
1. **Search bar overflowed off-screen on phones** — the single-row Activity/Where/search-button layout doesn't fit under ~640px. Added a `@media (max-width: 640px)` breakpoint that stacks the two input groups full-width and makes the search button its own full-width row.
2. **Map showed before any results on mobile** — `#main-content.visible { flex-direction: column-reverse }` put the 400px map above the list on small screens. Changed to `column` (list first) and shrunk the map to 280px — parents scan classes first, map is secondary.
3. **7 filter controls wrapped into 6 stacked rows**, pushing the result count and first card far down the page. Changed `.filter-bar` to a horizontally-scrollable single row on mobile (`overflow-x: auto`, hidden scrollbar, `flex-shrink: 0` on each pill) — same pattern Airbnb-style filter chips use.

Added **Leaflet.markercluster** (via CDN, same zero-build pattern as Leaflet itself: `unpkg.com/leaflet.markercluster@1.5.3`) to fix pin clutter — with 550+ Ireland-wide results, showing every marker individually was an unreadable overlapping mess. Nearby markers now collapse into a numbered cluster circle that splits apart on zoom/click. This was the right fix for "too many pins on screen at once" — **not** pagination or progressive-scroll-loading, since the problem is visual density in one viewport, not how much data is loaded (all markers are already fetched client-side in one query regardless). Implementation: replaced `L.featureGroup()` with `L.markerClusterGroup({maxClusterRadius: 50})` in `updateMap()`; the old `mapMarkers` array (used only to manually remove markers before re-render) was replaced with a single `markerClusterGroup` reference removed/recreated each render.

### Gotchas hit while fixing this

- **Chrome's `--headless --screenshot=file.png` CLI flag does not reliably respect `--window-size` for small viewports** — it produced a screenshot that looked like severe horizontal overflow (search button rendered as a giant misshapen blob, everything cut off at a hard edge) that was **not real** — confirmed via CDP (`Emulation.setDeviceMetricsOverride` + `Runtime.evaluate` measuring `document.body.scrollWidth` vs `window.innerWidth`) that the actual rendered page had zero overflow at a properly-forced 390px viewport. If a `--screenshot`-mode capture looks badly broken in a way that doesn't match the CSS, don't trust it blindly — verify with a real CDP session (`Page.captureScreenshot` after `Emulation.setDeviceMetricsOverride`) before concluding there's a bug. No `chromium-cli`/Playwright available in this environment; a from-scratch CDP script via Python's `websocket-client` (installed into a scratch venv — global `pip install` is blocked by PEP 668 externally-managed-environment on this machine) works fine for this.
- **Real bug this surfaced along the way**: the search button's magnifying-glass `<svg>` had a `viewBox` but no explicit `width`/`height`. It happened to render fine inside the original fixed 54×54px button, but the moment the button became `width: 100%` for the mobile stacked layout, the SVG's browser-default intrinsic size (300×150) took over and rendered as a huge shape overflowing the button. Fixed by adding `.search-btn svg { width: 22px; height: 22px; }`. General lesson: inline SVGs without explicit dimensions are a latent bug waiting for their container's sizing constraints to change.

## Star ratings, 1-5 (2026-07-31)

Added a no-login star rating widget. Schema change required — `add_ratings_table.sql` (new file, repo root) creates `public.class_ratings` (class_id FK, voter_id text, rating smallint 1-5, unique(class_id, voter_id)) with RLS allowing public select/insert/update. **This file has not been run yet** — I can't execute DDL via the REST API (PostgREST only does CRUD on existing tables/views), so it needs to go through the Supabase SQL editor manually, same as `update_coordinates.sql` earlier. Until it's run, the site degrades gracefully: `loadRatings()` catches the "table not found" error and just shows "No ratings yet" / empty rating state everywhere — confirmed via console log, not just assumed.

Design notes:
- **No real anti-abuse** is possible without a login system — `voter_id` is a random UUID generated client-side and stored in `localStorage`, so it identifies a browser, not a person. Anyone can trivially submit unlimited ratings by clearing localStorage or scripting requests. This is called out explicitly in the SQL file's comments. Different from the earlier "Allow public insert on classes" security issue in kind, not just degree: worst-case abuse here is rating manipulation on a narrow table, not arbitrary content injection into the core directory data.
- Average rating display rounds to the nearest whole star for the star *graphic* but shows the precise average as text (e.g. "4.2 (12 ratings)") — avoided building a fractional/half-star clipped-overlay SVG technique to save time; the text carries the precision.
- The interactive 5-star input is pure CSS (no JS needed for hover/fill preview) using the classic radio-input trick: DOM order 5,4,3,2,1 + `flex-direction: row-reverse` + `label:hover ~ label` sibling selector. JS only handles the `change` event (via existing event delegation on `#directory-container`) to call `submitRating()`.
- Ratings need a real numeric `classes.id` to attach to via FK — the widget silently doesn't render (`ratingSectionHtml` returns `''`) for any row without one, which matters if the site ever falls back to the local JSON (those rows have no `id` field, same limitation as favorites' `getItemKey`).
- Submission is optimistic: `ratingsByClassId`/`myRatingsByClassId` update and re-render immediately, then the Supabase upsert (`on_conflict: 'class_id,voter_id'`) happens in the background; a failed upsert just logs a warning rather than rolling back the UI, since this is a low-stakes enhancement, not critical data.

While building this, consolidated the **4 separate `window.supabase.createClient(...)` calls** (one each in loadClasses, the claim form, and now loadRatings/submitRating) into a single `window.supabaseClient` created once at the top of the page. The duplicate-client pattern already existed before this session and was throwing a "Multiple GoTrueClient instances" console warning; fixed while already touching this code rather than compounding it with 2 more instances.

### CDP testing gotcha: wrong tab connected

While functionally testing the star-click flow via a from-scratch CDP script (see the mobile-layout section above for why: no chromium-cli/Playwright in this environment), the first attempts showed `document.location.href` as `chrome-extension://.../background.html` with an empty body — the script had connected to `tabs[0]` from `/json`, which in a fresh profile isn't reliably the actual page tab. **Fix: filter for `t.get("type") == "page"` before picking a target.** Also hit a hang from a race condition in the CDP script itself (not a site bug): a helper that drains `ws.recv()` until it sees a specific reply `id` will silently swallow *other* messages (like a `Page.loadEventFired` event) that arrive during that wait — so a separate loop waiting for that same event afterward can hang forever. Fixed by using a flat `time.sleep()` instead of waiting for the specific event. `websocket-client` isn't installed globally (PEP 668 blocks global pip install on this machine) — use a scratch venv (`python3 -m venv`) for one-off CDP scripting needs.

## Expandable card details (2026-07-31)

Added click-to-expand on class cards — grows in place to show schedule, price/pricing details, age range, supervision type, class types, contact info, facilities, booking link, and a "Verified [date]" badge, all from fields that were already in the data but never displayed. No new page/route (kept the deferred SEO/per-class-page decision above untouched — this is pure client-side UI state).

- Whole card is clickable to toggle `.expanded`, plus an explicit "Show more details ▾" button for discoverability/keyboard access. Click delegation excludes `a` (Visit Website / booking link) and `.star-input` (rating widget) from toggling expand, and the favorite-button/claim-button handlers already `return` before reaching the toggle logic.
- Expand/collapse is a CSS `max-height` + `opacity` transition (classic technique — animating `height`/`max-height` to `auto` isn't natively animatable, so a generously large fixed max-height, here 900px, stands in for it).
- `#directory-container` needed `align-items: start` added — CSS Grid's default `stretch` would otherwise force every card in the same row to match the height of whichever one is expanded.
- Found and fixed a real **pre-existing latent bug** while touching this: `filterClasses`'s day-of-week filter did `item.days_of_week.toLowerCase()`, but `days_of_week` is an array (Postgres `text[]`), not a string — `.toLowerCase` doesn't exist on arrays, so selecting "Weekdays" or "Weekends" in the Day filter would have thrown. Never caught earlier because no test session happened to select that filter. Fixed by joining the array to a string first.
- Verified the whole interaction via CDP click simulation (not just code review): card-body click expands/collapses correctly, favorite-button and star-rating clicks correctly do *not* trigger expand (while still doing their own thing — favorite toggled, rating unaffected), the expand-toggle button works and renders real formatted content, and clicking "Visit Website" leaves the expanded state untouched.
- **Bug found after initial testing**: the exclusion only covered `.star-input` itself, missing the read-only `.rating-summary` (average stars display) and `.rate-row` (the "Rate this:"/"Your rating:" label wrapping the star input) — clicking either of those fell through to the expand toggle. Fixed by excluding `.rating-summary, .rate-row` instead of just `.star-input`.

### Testing gotcha: CDP click tests write real rows to production

Each CDP test run used a fresh `--user-data-dir` profile, so the site's `getOrCreateVoterId()` generated a brand-new random UUID every time — meaning every test click on a star rating submitted a **real, indistinguishable-from-genuine** row to the live `class_ratings` table (unlike the earlier `test-verify-voter` curl test, which was at least identifiably fake by voter_id). Ended up with 7 test rows polluting the table, all from today's testing, none genuine. Cleaned up with `delete from public.class_ratings;` in the SQL editor, since 100% of the table's content at that point was test data (feature had only gone live that same day). Lesson: when a feature writes to a live table, either reuse a fixed/obviously-fake voter/test ID across test runs (easy to `delete where voter_id = ...` after), or clean up test-inserted rows immediately after verifying rather than leaving them.

## Deferred: per-class detail pages (2026-07-31)

Discussed adding a page per class (fixes truncated descriptions, surfaces unused fields like pricing/facilities/schedule, gives shareable links). Deliberately **not building yet** — user wants to wait until there's a permanent domain/host, since real SEO benefit needs statically-generated per-class pages, and doing that against a throwaway/temporary domain means redoing the indexing work later. Revisit once hosting is settled.
