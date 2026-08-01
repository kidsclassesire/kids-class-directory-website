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
import re
from collections import Counter, defaultdict
from datetime import date

from generate_business_pages import (
    esc, fetch_all_rows, format_price, format_schedule, image_html,
    make_slug, self_validate_json_ld, slugify, REPO_ROOT, SITE_URL,
)

CLASSES_DIR = REPO_ROOT / 'classes'

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


def derive_county(address):
    # Rightmost county-name match wins: Irish addresses put the real locality
    # last, right before the eircode, so "1 Kildare St. Dublin 2" (a real row
    # in this data) must resolve to Dublin, not Kildare (a street name).
    if not address:
        return None
    matches = list(COUNTY_RE.finditer(address))
    return matches[-1].group(1).title() if matches else None


def category_slug(cat):
    return slugify(cat)


def county_slug(county):
    return slugify(county)


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

    meta_bits = [b for b in [format_schedule(row), format_price(row)] if b]
    meta_line = f'<div class="landing-card-meta">{" &middot; ".join(meta_bits)}</div>' if meta_bits else ''

    return f'''<div class="landing-card">
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
    return ''.join(landing_card_html(r, tag_kind) for r in rows)


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


def render_landing_page(title, canonical, meta_desc, breadcrumb_html, h1, intro_html, crosslinks_html, grid_html, json_ld_str):
    json_ld_block = f'<script type="application/ld+json">{json_ld_str}</script>' if json_ld_str else ''
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{esc(title)}</title>
    <meta name="description" content="{esc(meta_desc)}">
    <link rel="canonical" href="{canonical}">
    <meta property="og:title" content="{esc(title)}">
    <meta property="og:description" content="{esc(meta_desc)}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{canonical}">
    <meta property="og:image" content="{SITE_URL}/og-image.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{esc(title)}">
    <meta name="twitter:description" content="{esc(meta_desc)}">
    <link rel="stylesheet" href="../styles.css">
    {json_ld_block}
</head>
<body>
    <div class="landing-page">
        <a href="../index.html" class="brand-logo" style="display:inline-block;">Kids Patch</a>
        {breadcrumb_html}
        <h1>{esc(h1)}</h1>
        {intro_html}
        {crosslinks_html}
        <div class="landing-grid">{grid_html}</div>
    </div>
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
        f'<a href="index.html">All Classes</a> &rsaquo; {esc(cat)}</nav>'
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
    ld = landing_json_ld(h1, canonical, meta_desc, rows)

    page_html = render_landing_page(title, canonical, meta_desc, breadcrumb, h1, intro, crosslinks, grid, ld)
    self_validate_json_ld(page_html, f'classes/{slug}')
    return slug, page_html


def render_county_page(county, rows, combo_cats_for_county):
    slug = county_slug(county)
    canonical = f'{SITE_URL}/classes/{slug}.html'
    title = f'Kids Classes in {county} | Kids Patch'
    count = len(rows)
    meta_desc = truncate(
        f'Browse {count} kids classes and activities in {county}, Ireland. '
        'Filter by category, age and schedule to find the right class.'
    )

    breadcrumb = (
        f'<nav class="breadcrumb"><a href="../index.html">Home</a> &rsaquo; '
        f'<a href="index.html">All Classes</a> &rsaquo; {esc(county)}</nav>'
    )
    h1 = f'Kids Classes in {county}'

    top_cats = Counter(combo_cats_for_county).most_common(3)
    intro = f'<p class="landing-intro">Browse {count} kids classes and activities in {esc(county)}.'
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
        crosslinks = f'<div class="landing-crosslinks"><h2>Browse classes in {esc(county)} by category</h2><div class="crosslink-list">{links_html}</div></div>'

    grid = landing_grid_html(rows, tag_kind='category')
    ld = landing_json_ld(h1, canonical, meta_desc, rows)

    page_html = render_landing_page(title, canonical, meta_desc, breadcrumb, h1, intro, crosslinks, grid, ld)
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
        f'<a href="index.html">All Classes</a> &rsaquo; '
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
    ld = landing_json_ld(h1, canonical, meta_desc, rows)

    page_html = render_landing_page(title, canonical, meta_desc, breadcrumb, h1, intro, crosslinks, grid, ld)
    self_validate_json_ld(page_html, f'classes/{slug}')
    return slug, page_html


def render_hub_page(category_pages, county_pages):
    canonical = f'{SITE_URL}/classes/index.html'
    title = 'Browse All Kids Classes by Category & County | Kids Patch'
    meta_desc = (
        'Browse kids classes and activities across Ireland by category or county '
        '-- sports, dance, music, STEM and more, in every county.'
    )
    breadcrumb = '<nav class="breadcrumb"><a href="../index.html">Home</a> &rsaquo; All Classes</nav>'
    h1 = 'Browse All Classes by Category & County'
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

    for county, county_rows in sorted(rows_by_county.items()):
        if len(county_rows) < MIN_COUNTY:
            continue
        slug, page_html = render_county_page(county, county_rows, combo_cats_by_county.get(county, {}))
        (CLASSES_DIR / f'{slug}.html').write_text(page_html, encoding='utf-8')
        landing_paths.append(f'classes/{slug}.html')
        county_pages.append((county, slug))

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
          f'({len(category_pages)} category, {len(county_pages)} county, {combo_count} combo, 1 hub).')

    manifest = json.loads((REPO_ROOT / 'business-index.json').read_text())
    today = date.today().isoformat()
    url_entries = [f'{SITE_URL}/']
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
