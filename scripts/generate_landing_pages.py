"""Generates category, county, and combined category+county landing pages
under classes/, plus the hub page classes/index.html, and rewrites the final
merged sitemap.xml (homepage + business pages + landing pages).

Must run AFTER generate_business_pages.py in the same checkout -- reads
business-index.json for the merged sitemap, and uses the identical
make_slug() (imported, not reimplemented) so every business-page link here
matches what that script actually wrote, by construction.

Run locally: python3 scripts/generate_business_pages.py && python3 scripts/generate_landing_pages.py
Also run by .github/workflows/build-business-pages.yml.
"""

import json
import math
import re
from collections import Counter, defaultdict
from datetime import date

from generate_business_pages import (
    esc, fetch_all_rows, file_version, format_price, format_schedule, image_html,
    make_slug, self_validate_json_ld, slugify, REPO_ROOT, SITE_URL, STYLES_VERSION,
    ANALYTICS_JS_VERSION, SITE_HEADER_HTML, SITE_FOOTER_HTML,
)

CLASSES_DIR = REPO_ROOT / 'classes'
RANGE_SLIDER_JS_VERSION = file_version('range-slider.js')
LANDING_FILTERS_JS_VERSION = file_version('landing-filters.js')

# Structured price_amount is only populated on ~2% of rows -- the far more
# common signal for "this is free" is prose in pricing_details/pricing_basis
# ("Price: Free", "Per Family: FREE", etc, mostly library/council listings).
# Checked by hand against a sample: this combination doesn't false-positive on
# "free trial then paid" language because that phrasing lives in the long-form
# description field, not these two structured fields.
FREE_TEXT_RE = re.compile(r'\bfree\b', re.IGNORECASE)


def is_free(row):
    if row.get('price_amount') == 0:
        return True
    text = ' '.join(filter(None, [row.get('pricing_details'), row.get('pricing_basis')]))
    return bool(FREE_TEXT_RE.search(text))


MIN_NATIONWIDE = 3
MIN_COUNTY = 3
MIN_COMBO = 4

IRISH_COUNTIES = [
    'Carlow', 'Cavan', 'Clare', 'Cork', 'Donegal', 'Dublin', 'Galway', 'Kerry',
    'Kildare', 'Kilkenny', 'Laois', 'Leitrim', 'Limerick', 'Longford', 'Louth',
    'Mayo', 'Meath', 'Monaghan', 'Offaly', 'Roscommon', 'Sligo', 'Tipperary',
    'Waterford', 'Westmeath', 'Wexford', 'Wicklow',
]
COUNTY_RE = re.compile(r'\b(' + '|'.join(IRISH_COUNTIES) + r')\b', re.IGNORECASE)

# Counties whose namesake town/city is a distinct, high-volume search target of its
# own (e.g. "Cork city" vs "county Cork"). Label/slug pairs mirror how these are
# actually referred to locally -- "City" for the five with city status, "Town" for
# the rest -- and are distinct from the plain county slug on purpose so they don't
# collide with e.g. classes/cork.html.
COUNTY_TOWN_PAGES = {
    'Cork': ('Cork City', 'cork-city'),
    'Galway': ('Galway City', 'galway-city'),
    'Limerick': ('Limerick City', 'limerick-city'),
    'Waterford': ('Waterford City', 'waterford-city'),
    'Kilkenny': ('Kilkenny City', 'kilkenny-city'),
    'Wexford': ('Wexford Town', 'wexford-town'),
    'Sligo': ('Sligo Town', 'sligo-town'),
    'Carlow': ('Carlow Town', 'carlow-town'),
}


def is_county_town_address(address, county):
    # Irish addresses reliably distinguish the county town itself from the rest of
    # the county by whether "Co."/"County" prefixes the name: "Cork, T23 ..." is
    # the city; "Bandon, County Cork" is not. A bare comma-segment exactly matching
    # the county name (no Co./County prefix in that segment) signals the former.
    if not address:
        return False
    return any(part.strip().lower() == county.lower() for part in address.split(','))


def derive_county(address):
    # Rightmost county-name match wins: Irish addresses put the real locality
    # last, right before the eircode, so "1 Kildare St. Dublin 2" (a real row
    # in this data) must resolve to Dublin, not Kildare (a street name).
    if not address:
        return None
    matches = list(COUNTY_RE.finditer(address))
    return matches[-1].group(1).title() if matches else None


# Curated candidate towns for their own landing page, each tied to its county so a
# town match can be cross-checked against the row's already-derived county (guards
# against a same-named place in a different county being mis-filed). None of these
# share a name with their own county -- those (Cork, Galway, Sligo, etc.) are
# handled separately by COUNTY_TOWN_PAGES/is_county_town_address, since a bare
# regex match on e.g. "Cork" can't tell "Cork city" apart from "County Cork".
# Deliberately curated rather than derived from raw address parsing (which also
# turns up street names, school names and townlands as false positives) -- adding
# a town here doesn't guarantee it gets a page, MIN_TOWN below still gates that.
TOWN_COUNTY = {
    'Drogheda': 'Louth', 'Dundalk': 'Louth',
    'Portlaoise': 'Laois', 'Portarlington': 'Laois',
    'Tralee': 'Kerry', 'Killarney': 'Kerry',
    'Clonmel': 'Tipperary', 'Nenagh': 'Tipperary', 'Roscrea': 'Tipperary',
    'Thurles': 'Tipperary', 'Carrick-on-Suir': 'Tipperary',
    'Navan': 'Meath', 'Dunboyne': 'Meath', 'Ratoath': 'Meath', 'Kells': 'Meath',
    'Mullingar': 'Westmeath', 'Athlone': 'Westmeath',
    'Ennis': 'Clare', 'Shannon': 'Clare',
    'Cobh': 'Cork', 'Clonakilty': 'Cork', 'Ballincollig': 'Cork', 'Midleton': 'Cork',
    'Carrigtwohill': 'Cork', 'Kinsale': 'Cork', 'Mallow': 'Cork',
    'Ballinasloe': 'Galway', 'Oranmore': 'Galway', 'Tuam': 'Galway',
    'Letterkenny': 'Donegal', 'Buncrana': 'Donegal',
    'Bray': 'Wicklow', 'Greystones': 'Wicklow', 'Arklow': 'Wicklow',
    'Ballina': 'Mayo', 'Castlebar': 'Mayo', 'Westport': 'Mayo',
    'Dungarvan': 'Waterford', 'Tramore': 'Waterford',
    'New Ross': 'Wexford', 'Enniscorthy': 'Wexford', 'Gorey': 'Wexford',
    'Tullamore': 'Offaly', 'Birr': 'Offaly',
    'Naas': 'Kildare', 'Maynooth': 'Kildare', 'Celbridge': 'Kildare',
    'Newbridge': 'Kildare', 'Leixlip': 'Kildare',
    # Dublin suburbs with their own independent search identity, distinct from a
    # generic "Dublin" search -- these dominate the raw address-frequency counts.
    'Tallaght': 'Dublin', 'Swords': 'Dublin', 'Balbriggan': 'Dublin', 'Dundrum': 'Dublin',
    'Rathfarnham': 'Dublin', 'Rathmines': 'Dublin', 'Blanchardstown': 'Dublin',
    'Terenure': 'Dublin', 'Malahide': 'Dublin', 'Templeogue': 'Dublin',
    'Stillorgan': 'Dublin', 'Firhouse': 'Dublin', 'Dalkey': 'Dublin', 'Clontarf': 'Dublin',
    'Clondalkin': 'Dublin', 'Skerries': 'Dublin', 'Castleknock': 'Dublin',
    'Knocklyon': 'Dublin', 'Drumcondra': 'Dublin', 'Monkstown': 'Dublin',
    'Sandymount': 'Dublin', 'Lucan': 'Dublin', 'Mount Merrion': 'Dublin',
    'Kilternan': 'Dublin', 'Shankill': 'Dublin', 'Foxrock': 'Dublin', 'Ballsbridge': 'Dublin',
    'Lusk': 'Dublin', 'Dun Laoghaire': 'Dublin', 'Ballinteer': 'Dublin',
    'Blackrock': 'Dublin', 'Sandyford': 'Dublin',
    'Rathgar': 'Dublin', 'Crumlin': 'Dublin', 'Ranelagh': 'Dublin', 'Milltown': 'Dublin',
    # North County Dublin coast + Southside coastal infill (2026-08-05 expansion batch).
    'Howth': 'Dublin', 'Sutton': 'Dublin', 'Baldoyle': 'Dublin', 'Portmarnock': 'Dublin',
    'Donabate': 'Dublin', 'Rush': 'Dublin', 'Killiney': 'Dublin', 'Glenageary': 'Dublin',
    'Cabinteely': 'Dublin', 'Stepaside': 'Dublin', 'Deansgrange': 'Dublin',
    'Loughlinstown': 'Dublin',
    # West Dublin infill.
    'Palmerstown': 'Dublin', 'Chapelizod': 'Dublin', 'Inchicore': 'Dublin',
    'Kilmainham': 'Dublin', 'Clonsilla': 'Dublin', 'Ongar': 'Dublin', 'Hartstown': 'Dublin',
    'Corduff': 'Dublin',
    # Northside infill.
    'Glasnevin': 'Dublin', 'Phibsborough': 'Dublin', 'Marino': 'Dublin', 'Fairview': 'Dublin',
    'Cabra': 'Dublin', 'Raheny': 'Dublin', 'Donaghmede': 'Dublin', 'Kilbarrack': 'Dublin',
    'Artane': 'Dublin', 'Coolock': 'Dublin', 'Santry': 'Dublin', 'Finglas': 'Dublin',
    'Ballymun': 'Dublin',
}
TOWN_LABEL_BY_LOWER = {name.lower(): name for name in TOWN_COUNTY}
TOWN_RE = re.compile(
    r'\b(' + '|'.join(re.escape(n) for n in sorted(TOWN_COUNTY, key=len, reverse=True)) + r')\b',
    re.IGNORECASE,
)
MIN_TOWN = 4


def derive_town(address, expected_county):
    # Same rightmost-match convention as derive_county, plus a cross-check against
    # the county already derived for this row -- a coincidental match against the
    # wrong county's town (e.g. a same-named street) is discarded rather than
    # mis-filing the row under the wrong town page.
    if not address or not expected_county:
        return None
    matches = list(TOWN_RE.finditer(address))
    if not matches:
        return None
    label = TOWN_LABEL_BY_LOWER[matches[-1].group(1).lower()]
    return label if TOWN_COUNTY[label] == expected_county else None


def category_slug(cat):
    return slugify(cat)


def county_slug(county):
    return slugify(county)


def town_slug(town):
    return slugify(town)


def combo_slug(cat, county):
    return f'{category_slug(cat)}-{county_slug(county)}'


def truncate(desc, limit=160):
    if len(desc) <= limit:
        return desc
    return desc[:limit - 3].rsplit(' ', 1)[0] + '...'


def landing_card_html(row, tag_kind):
    company = esc(row.get('company_name'))
    tag_html = ''
    if tag_kind == 'category' and row.get('category'):
        tag_html = f'<div class="tag-container"><span class="tag">{esc(row["category"])}</span></div>'
    elif tag_kind == 'county' and row.get('_county'):
        tag_html = f'<div class="tag-container"><span class="tag">{esc(row["_county"])}</span></div>'

    # format_schedule() already escapes its own parts internally (see its
    # docstring comment) -- format_price() doesn't, so it's escaped here.
    meta_bits = [b for b in [format_schedule(row), esc(format_price(row))] if b]
    meta_line = f'<div class="landing-card-meta">{" &middot; ".join(meta_bits)}</div>' if meta_bits else ''

    return f'''<div class="landing-card" data-id="{row['id']}">
        <div class="card-image">{image_html(row)}</div>
        <div class="card-content">
            <h3>{company}</h3>
            {tag_html}
            <p class="description">{esc(row.get('description')) or 'No description available.'}</p>
            {meta_line}
            <a href="../business/{make_slug(row)}.html" class="button">View full details &rarr;</a>
        </div>
    </div>'''


def landing_grid_html(rows, tag_kind):
    cards = landing_grid_html_cards(rows, tag_kind)
    no_results = (
        '<p class="no-results" id="no-results-message" hidden>'
        'No classes match your filters. <button type="button" id="no-results-reset">Clear filters</button></p>'
    )
    return f'{cards}{no_results}'


def landing_grid_html_cards(rows, tag_kind):
    return ''.join(landing_card_html(r, tag_kind) for r in rows)


def landing_dataset_json(rows):
    # Single embedded dataset shared by the map and the age/price/free
    # filters (landing-filters.js) -- one source of truth instead of
    # duplicating fields across data-* attributes and a separate map-only
    # blob. Includes every row, not just geocoded ones, since filtering
    # must apply to cards with no coordinates too.
    points = [
        {
            'id': r['id'],
            'lat': r.get('latitude'),
            'lon': r.get('longitude'),
            'name': r.get('company_name') or '',
            'category': r.get('category') or '',
            'url': f"../business/{make_slug(r)}.html",
            'minAge': r.get('minimum_age'),
            'maxAge': r.get('maximum_age'),
            'price': r.get('price_amount'),
            'free': is_free(r),
        }
        for r in rows
    ]
    data_json = json.dumps(points, ensure_ascii=False).replace('</', '<\\/')
    return f'<script type="application/json" id="landing-data">{data_json}</script>'


def landing_map_div_html(rows):
    has_geo = any(r.get('latitude') is not None and r.get('longitude') is not None for r in rows)
    if not has_geo:
        return ''
    return '<div class="landing-map-wrap"><div id="landing-map" class="landing-map"></div></div>'


def landing_filters_html(rows):
    known_prices = [r['price_amount'] for r in rows if isinstance(r.get('price_amount'), (int, float))]
    max_price = max(50, int(math.ceil(max(known_prices) / 10.0)) * 10) if known_prices else 50

    known_ages = [a for r in rows for a in (r.get('minimum_age'), r.get('maximum_age')) if isinstance(a, (int, float))]
    max_age = max(18, int(math.ceil(max(known_ages)))) if known_ages else 18

    return f'''<div class="landing-filters" id="landing-filters">
        <div class="filter-group">
            <div class="filter-label"><span>Age</span><span class="filter-value" id="age-filter-value">Any age</span></div>
            <div class="range-slider" data-min="0" data-max="{max_age}">
                <div class="range-track"><div class="range-track-fill" id="age-track-fill"></div></div>
                <input type="range" min="0" max="{max_age}" value="0" step="1" id="age-min" aria-label="Minimum age">
                <input type="range" min="0" max="{max_age}" value="{max_age}" step="1" id="age-max" aria-label="Maximum age">
            </div>
        </div>
        <div class="filter-group">
            <div class="filter-label"><span>Price</span><span class="filter-value" id="price-filter-value">Any price</span></div>
            <div class="range-slider" data-min="0" data-max="{max_price}">
                <div class="range-track"><div class="range-track-fill" id="price-track-fill"></div></div>
                <input type="range" min="0" max="{max_price}" value="0" step="1" id="price-min" aria-label="Minimum price">
                <input type="range" min="0" max="{max_price}" value="{max_price}" step="1" id="price-max" aria-label="Maximum price">
            </div>
            <div class="filter-hint">Classes with unlisted pricing are always shown</div>
        </div>
        <div class="filter-group filter-group-checkbox">
            <label class="filter-checkbox"><input type="checkbox" id="free-only"> Free classes only</label>
        </div>
        <div class="filters-footer">
            <div class="filters-count" id="filters-count"></div>
            <button type="button" id="filters-reset" class="filters-reset" hidden>Reset filters</button>
        </div>
    </div>'''


def landing_json_ld(name, canonical, desc, rows):
    ld = {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        'name': name,
        'description': desc,
        'url': canonical,
        'mainEntity': {
            '@type': 'ItemList',
            'numberOfItems': len(rows),
            'itemListElement': [
                {
                    '@type': 'ListItem',
                    'position': i + 1,
                    'url': f'{SITE_URL}/business/{make_slug(r)}.html',
                    'name': r.get('company_name'),
                }
                for i, r in enumerate(rows)
            ],
        },
    }
    return json.dumps(ld, ensure_ascii=False).replace('</', '<\\/')


def render_landing_page(title, canonical, meta_desc, breadcrumb_html, h1, intro_html, crosslinks_html, grid_html, json_ld_str, map_html='', filters_html='', dataset_html=''):
    json_ld_block = f'<script type="application/ld+json">{json_ld_str}</script>' if json_ld_str else ''
    leaflet_css = ''
    leaflet_scripts = ''
    if map_html:
        leaflet_css = (
            '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin=""/>\n'
            '    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css"/>\n'
            '    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css"/>\n    '
        )
        leaflet_scripts = (
            '\n    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>'
            '\n    <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>'
        )
    filters_scripts = ''
    if dataset_html:
        filters_scripts = (
            '\n    <script src="../analytics.js?v=' + ANALYTICS_JS_VERSION + '" defer></script>'
            # Must precede landing-filters.js (both deferred, so document order
            # is execution order) -- it defines setupRangeSlider as a plain
            # global function that landing-filters.js calls directly.
            '\n    <script src="../range-slider.js?v=' + RANGE_SLIDER_JS_VERSION + '" defer></script>'
            '\n    <script src="../landing-filters.js?v=' + LANDING_FILTERS_JS_VERSION + '" defer></script>'
        )
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-81P6V4P1WX"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){{dataLayer.push(arguments);}}
        gtag('js', new Date());
        gtag('config', 'G-81P6V4P1WX');
    </script>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{esc(title)}</title>
    <meta name="description" content="{esc(meta_desc)}">
    <link rel="canonical" href="{canonical}">
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="48x48" href="/favicon-48x48.png">
    <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
    <link rel="manifest" href="/site.webmanifest">
    <meta property="og:title" content="{esc(title)}">
    <meta property="og:description" content="{esc(meta_desc)}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{canonical}">
    <meta property="og:image" content="{SITE_URL}/og-image.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{esc(title)}">
    <meta name="twitter:description" content="{esc(meta_desc)}">
    {leaflet_css}<link rel="stylesheet" href="../styles.css?v={STYLES_VERSION}">
    {json_ld_block}
</head>
<body>
{SITE_HEADER_HTML}
    <div class="landing-page">
        {breadcrumb_html}
        <h1>{esc(h1)}</h1>
        {intro_html}
        {crosslinks_html}
        {filters_html}
        {map_html}
        <div class="landing-grid">{grid_html}</div>
        {dataset_html}
    </div>
{SITE_FOOTER_HTML}{leaflet_scripts}{filters_scripts}
</body>
</html>'''


def render_category_page(cat, rows, combo_counties_for_cat):
    slug = category_slug(cat)
    canonical = f'{SITE_URL}/classes/{slug}.html'
    title = f'{cat} Classes for Kids in Ireland | Kids Patch'
    count = len(rows)
    meta_desc = truncate(
        f'Find {count} {cat} classes and activities for kids across Ireland. '
        'Compare schedules, ages and pricing, then contact providers directly.'
    )

    breadcrumb = (
        f'<nav class="breadcrumb"><a href="../index.html">Home</a> &rsaquo; '
        f'<a href="index.html">All Activities</a> &rsaquo; {esc(cat)}</nav>'
    )
    h1 = f'{cat} Classes in Ireland'

    top_counties = Counter(combo_counties_for_cat).most_common(3)
    intro = f'<p class="landing-intro">Explore {count} {esc(cat)} classes and activities for kids across Ireland.'
    if top_counties:
        top_txt = ', '.join(c for c, _ in top_counties)
        intro += f' {esc(cat)} classes are most widely available in {esc(top_txt)}.'
    intro += '</p>'

    combo_links = [
        (county, f'{combo_slug(cat, county)}.html')
        for county, n in sorted(combo_counties_for_cat.items())
        if n >= MIN_COMBO
    ]
    crosslinks = ''
    if combo_links:
        links_html = ''.join(f'<a href="{path}">{esc(county)}</a>' for county, path in combo_links)
        crosslinks = f'<div class="landing-crosslinks"><h2>Browse {esc(cat)} by county</h2><div class="crosslink-list">{links_html}</div></div>'

    grid = landing_grid_html(rows, tag_kind='county')
    map_html = landing_map_div_html(rows)
    filters_html = landing_filters_html(rows)
    dataset_html = landing_dataset_json(rows)
    ld = landing_json_ld(h1, canonical, meta_desc, rows)

    page_html = render_landing_page(title, canonical, meta_desc, breadcrumb, h1, intro, crosslinks, grid, ld, map_html=map_html, filters_html=filters_html, dataset_html=dataset_html)
    self_validate_json_ld(page_html, f'classes/{slug}')
    return slug, page_html


def render_county_page(county, rows, combo_cats_for_county, citytowns=None):
    slug = county_slug(county)
    canonical = f'{SITE_URL}/classes/{slug}.html'
    title = f'Kids Activities in {county} | Kids Patch'
    count = len(rows)
    meta_desc = truncate(
        f'Browse {count} kids activities and classes in {county}, Ireland. '
        'Filter by category, age and schedule to find the right activity.'
    )

    breadcrumb = (
        f'<nav class="breadcrumb"><a href="../index.html">Home</a> &rsaquo; '
        f'<a href="index.html">All Activities</a> &rsaquo; {esc(county)}</nav>'
    )
    h1 = f'Kids Activities in {county}'

    top_cats = Counter(combo_cats_for_county).most_common(3)
    intro = f'<p class="landing-intro">Browse {count} kids activities and classes in {esc(county)}.'
    if top_cats:
        top_txt = ', '.join(c for c, _ in top_cats)
        intro += f' Popular categories in {esc(county)} include {esc(top_txt)}.'
    intro += '</p>'

    combo_links = [
        (cat, f'{combo_slug(cat, county)}.html')
        for cat, n in sorted(combo_cats_for_county.items())
        if n >= MIN_COMBO
    ]
    crosslinks = ''
    if combo_links:
        links_html = ''.join(f'<a href="{path}">{esc(cat)}</a>' for cat, path in combo_links)
        crosslinks = f'<div class="landing-crosslinks"><h2>Browse activities in {esc(county)} by category</h2><div class="crosslink-list">{links_html}</div></div>'

    if citytowns:
        town_links_html = ''.join(f'<a href="{ct_slug}.html">{esc(label)}</a>' for label, ct_slug in sorted(citytowns))
        crosslinks += f'<div class="landing-crosslinks"><h2>Browse activities in {esc(county)} by town</h2><div class="crosslink-list">{town_links_html}</div></div>'

    grid = landing_grid_html(rows, tag_kind='category')
    map_html = landing_map_div_html(rows)
    filters_html = landing_filters_html(rows)
    dataset_html = landing_dataset_json(rows)
    ld = landing_json_ld(h1, canonical, meta_desc, rows)

    page_html = render_landing_page(title, canonical, meta_desc, breadcrumb, h1, intro, crosslinks, grid, ld, map_html=map_html, filters_html=filters_html, dataset_html=dataset_html)
    self_validate_json_ld(page_html, f'classes/{slug}')
    return slug, page_html


def render_citytown_page(county, label, slug, rows):
    canonical = f'{SITE_URL}/classes/{slug}.html'
    title = f'Kids Activities in {label} | Kids Patch'
    count = len(rows)
    meta_desc = truncate(
        f'Browse {count} kids activities and classes in {label}, Ireland. '
        'Filter by category, age and schedule to find the right activity.'
    )

    county_slug_ = county_slug(county)
    breadcrumb = (
        f'<nav class="breadcrumb"><a href="../index.html">Home</a> &rsaquo; '
        f'<a href="index.html">All Activities</a> &rsaquo; '
        f'<a href="{county_slug_}.html">{esc(county)}</a> &rsaquo; {esc(label)}</nav>'
    )
    h1 = f'Kids Activities in {label}'
    intro = (
        f'<p class="landing-intro">Browse {count} kids activities and classes in {esc(label)}. '
        'Compare schedules, ages and pricing below, or contact a provider directly to book.</p>'
    )
    crosslinks = (
        '<div class="business-backlinks">'
        f'<a href="{county_slug_}.html">&larr; All activities in County {esc(county)}</a>'
        '</div>'
    )

    grid = landing_grid_html(rows, tag_kind='category')
    map_html = landing_map_div_html(rows)
    filters_html = landing_filters_html(rows)
    dataset_html = landing_dataset_json(rows)
    ld = landing_json_ld(h1, canonical, meta_desc, rows)

    page_html = render_landing_page(title, canonical, meta_desc, breadcrumb, h1, intro, crosslinks, grid, ld, map_html=map_html, filters_html=filters_html, dataset_html=dataset_html)
    self_validate_json_ld(page_html, f'classes/{slug}')
    return slug, page_html


def render_combo_page(cat, county, rows):
    slug = combo_slug(cat, county)
    canonical = f'{SITE_URL}/classes/{slug}.html'
    title = f'{cat} Classes in {county} | Kids Patch'
    count = len(rows)
    meta_desc = truncate(
        f'Find {count} {cat} classes for kids in {county}. '
        'Compare schedules, ages and pricing, then contact providers directly.'
    )

    breadcrumb = (
        f'<nav class="breadcrumb"><a href="../index.html">Home</a> &rsaquo; '
        f'<a href="index.html">All Activities</a> &rsaquo; '
        f'<a href="{category_slug(cat)}.html">{esc(cat)}</a> &rsaquo; {esc(county)}</nav>'
    )
    h1 = f'{cat} Classes in {county}'
    intro = (
        f'<p class="landing-intro">Explore {count} {esc(cat)} classes for kids in {esc(county)}, Ireland. '
        'Compare schedules, ages and pricing below, or contact a provider directly to book.</p>'
    )

    crosslinks = (
        '<div class="business-backlinks">'
        f'<a href="{category_slug(cat)}.html">&larr; All {esc(cat)} classes in Ireland</a>'
        f'<a href="{county_slug(county)}.html">&larr; All classes in {esc(county)}</a>'
        '</div>'
    )

    grid = landing_grid_html(rows, tag_kind=None)
    map_html = landing_map_div_html(rows)
    filters_html = landing_filters_html(rows)
    dataset_html = landing_dataset_json(rows)
    ld = landing_json_ld(h1, canonical, meta_desc, rows)

    page_html = render_landing_page(title, canonical, meta_desc, breadcrumb, h1, intro, crosslinks, grid, ld, map_html=map_html, filters_html=filters_html, dataset_html=dataset_html)
    self_validate_json_ld(page_html, f'classes/{slug}')
    return slug, page_html


def render_hub_page(category_pages, county_pages):
    canonical = f'{SITE_URL}/classes/index.html'
    title = 'Browse All Kids Activities by Category & County | Kids Patch'
    meta_desc = (
        'Browse kids activities and classes across Ireland by category or county '
        '-- sports, dance, music, STEM and more, in every county.'
    )
    breadcrumb = '<nav class="breadcrumb"><a href="../index.html">Home</a> &rsaquo; All Activities</nav>'
    h1 = 'Browse All Activities by Category & County'
    intro = '<p class="landing-intro">Pick a category or a county below to see the kids\' classes and activities available there.</p>'

    cat_links = ''.join(f'<a href="{slug}.html">{esc(cat)}</a>' for cat, slug in sorted(category_pages))
    county_links = ''.join(f'<a href="{slug}.html">{esc(county)}</a>' for county, slug in sorted(county_pages))
    crosslinks = (
        f'<div class="landing-crosslinks"><h2>Browse by category</h2><div class="crosslink-list">{cat_links}</div></div>'
        f'<div class="landing-crosslinks"><h2>Browse by county</h2><div class="crosslink-list">{county_links}</div></div>'
    )

    return render_landing_page(title, canonical, meta_desc, breadcrumb, h1, intro, crosslinks, '', '')


def main():
    print('Fetching rows from Supabase...')
    rows = fetch_all_rows()
    rows = [r for r in rows if r.get('company_name') and r.get('id') is not None]
    print(f'Fetched {len(rows)} usable rows.')

    for r in rows:
        r['_county'] = derive_county(r.get('address'))

    rows_by_category = defaultdict(list)
    rows_by_county = defaultdict(list)
    rows_by_combo = defaultdict(list)
    for r in rows:
        cat, county = r.get('category'), r.get('_county')
        if cat:
            rows_by_category[cat].append(r)
        if county:
            rows_by_county[county].append(r)
        if cat and county:
            rows_by_combo[(cat, county)].append(r)

    combo_counties_by_cat = defaultdict(dict)
    combo_cats_by_county = defaultdict(dict)
    for (cat, county), combo_rows in rows_by_combo.items():
        combo_counties_by_cat[cat][county] = len(combo_rows)
        combo_cats_by_county[county][cat] = len(combo_rows)

    CLASSES_DIR.mkdir(exist_ok=True)
    landing_paths = []
    category_pages, county_pages = [], []

    for cat, cat_rows in sorted(rows_by_category.items()):
        if len(cat_rows) < MIN_NATIONWIDE:
            continue
        slug, page_html = render_category_page(cat, cat_rows, combo_counties_by_cat.get(cat, {}))
        (CLASSES_DIR / f'{slug}.html').write_text(page_html, encoding='utf-8')
        landing_paths.append(f'classes/{slug}.html')
        category_pages.append((cat, slug))

    # County-town (namesake) pages: Cork City vs county Cork, etc. Can't use a
    # plain regex match here -- "Cork" also substring-matches "County Cork" --
    # so is_county_town_address() disambiguates via comma-segment instead.
    rows_by_citytown = defaultdict(list)
    for r in rows:
        county = r.get('_county')
        if county in COUNTY_TOWN_PAGES and is_county_town_address(r.get('address'), county):
            rows_by_citytown[county].append(r)

    # Generic town pages (Drogheda, Tralee, Dublin suburbs, ...): a plain regex
    # match against the curated TOWN_COUNTY list is safe here since none of these
    # share a name with their own county.
    rows_by_town = defaultdict(list)
    for r in rows:
        town = derive_town(r.get('address'), r.get('_county'))
        if town:
            rows_by_town[town].append(r)

    town_pages_by_county = defaultdict(list)  # county -> [(label, slug), ...] for county-page crosslinks
    town_page_jobs = []  # (county, label, slug, rows) actually worth rendering

    for county, (label, ct_slug) in COUNTY_TOWN_PAGES.items():
        ct_rows = rows_by_citytown.get(county, [])
        if len(ct_rows) >= MIN_COUNTY:
            town_pages_by_county[county].append((label, ct_slug))
            town_page_jobs.append((county, label, ct_slug, ct_rows))

    for town, town_rows in rows_by_town.items():
        if len(town_rows) < MIN_TOWN:
            continue
        county = TOWN_COUNTY[town]
        slug = town_slug(town)
        town_pages_by_county[county].append((town, slug))
        town_page_jobs.append((county, town, slug, town_rows))

    for county, county_rows in sorted(rows_by_county.items()):
        if len(county_rows) < MIN_COUNTY:
            continue
        slug, page_html = render_county_page(
            county, county_rows, combo_cats_by_county.get(county, {}), town_pages_by_county.get(county)
        )
        (CLASSES_DIR / f'{slug}.html').write_text(page_html, encoding='utf-8')
        landing_paths.append(f'classes/{slug}.html')
        county_pages.append((county, slug))

    for county, label, ct_slug, ct_rows in sorted(town_page_jobs, key=lambda job: (job[0], job[1])):
        _, page_html = render_citytown_page(county, label, ct_slug, ct_rows)
        (CLASSES_DIR / f'{ct_slug}.html').write_text(page_html, encoding='utf-8')
        landing_paths.append(f'classes/{ct_slug}.html')

    combo_count = 0
    for (cat, county), combo_rows in sorted(rows_by_combo.items()):
        if len(combo_rows) < MIN_COMBO:
            continue
        slug, page_html = render_combo_page(cat, county, combo_rows)
        (CLASSES_DIR / f'{slug}.html').write_text(page_html, encoding='utf-8')
        landing_paths.append(f'classes/{slug}.html')
        combo_count += 1

    hub_html = render_hub_page(category_pages, county_pages)
    (CLASSES_DIR / 'index.html').write_text(hub_html, encoding='utf-8')
    landing_paths.append('classes/index.html')

    assert len(landing_paths) == len(set(landing_paths)), 'duplicate landing page path(s) detected'

    print(f'Wrote {len(landing_paths)} landing pages '
          f'({len(category_pages)} category, {len(county_pages)} county, {len(town_page_jobs)} town, '
          f'{combo_count} combo, 1 hub).')

    manifest = json.loads((REPO_ROOT / 'business-index.json').read_text())
    today = date.today().isoformat()
    url_entries = [f'{SITE_URL}/', f'{SITE_URL}/contact.html']
    url_entries += [f'{SITE_URL}/{path}' for path in manifest.values()]
    url_entries += [f'{SITE_URL}/{path}' for path in landing_paths]

    urls_xml = '\n'.join(
        f'  <url>\n    <loc>{u}</loc>\n    <lastmod>{today}</lastmod>\n  </url>' for u in url_entries
    )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{urls_xml}\n</urlset>\n'
    )
    (REPO_ROOT / 'sitemap.xml').write_text(sitemap, encoding='utf-8')
    print(f'Merged sitemap.xml: {len(url_entries)} URLs '
          f'(1 homepage + {len(manifest)} business + {len(landing_paths)} landing).')


if __name__ == '__main__':
    main()
