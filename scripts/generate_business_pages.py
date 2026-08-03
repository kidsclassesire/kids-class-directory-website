"""Generates one static, crawlable HTML page per row in the `classes` table,
plus sitemap.xml and business-index.json (the slug manifest index.html links
to). Read-only against Supabase -- uses the public anon key, same one already
shipped in plaintext in index.html/portal.html (RLS restricts it to SELECT).

Run locally any time: python3 scripts/generate_business_pages.py
Also run nightly + on push by .github/workflows/build-business-pages.yml.
"""

import html
import json
import re
import urllib.error
import urllib.request
from datetime import date, timezone
from pathlib import Path
from urllib.parse import quote

SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co'
SUPABASE_ANON_KEY = 'sb_publishable_eduvbMySPxHPT0iZjE_LqQ_w6nyjnjY'
SITE_URL = 'https://www.kidspatch.ie'

REPO_ROOT = Path(__file__).resolve().parent.parent
BUSINESS_DIR = REPO_ROOT / 'business'


def fetch_all_rows():
    headers = {'apikey': SUPABASE_ANON_KEY, 'Authorization': f'Bearer {SUPABASE_ANON_KEY}'}
    rows, offset, page = [], 0, 1000
    while True:
        req = urllib.request.Request(
            f'{SUPABASE_URL}/rest/v1/classes?select=*&order=id',
            headers={**headers, 'Range-Unit': 'items', 'Range': f'{offset}-{offset + page - 1}'},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.loads(resp.read())
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows


def esc(value):
    return html.escape(str(value), quote=True) if value not in (None, '') else ''


def slugify(text):
    text = (text or '').lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = text.strip('-')
    text = re.sub(r'-{2,}', '-', text)
    return text[:60].rstrip('-') or 'business'


def make_slug(row):
    return f"{slugify(row.get('company_name'))}-{row['id']}"


def format_schedule(row):
    # Each part is escaped individually (not the joined result) so the
    # ' &middot; ' separator entity survives -- escaping it after joining
    # would double-encode it into '&amp;middot;'.
    parts = []
    days = row.get('days_of_week')
    if isinstance(days, list) and days:
        parts.append(esc(', '.join(days)))
    start, end = row.get('start_time'), row.get('end_time')
    if start:
        parts.append(f"{esc(start)}-{esc(end)}" if end else f"from {esc(start)}")
    if row.get('term_structure'):
        parts.append(esc(row['term_structure']))
    return ' &middot; '.join(parts)


def format_phone(value):
    # Source data has ~74 rows where phone_number was corrupted upstream into a
    # stringified float (e.g. "353863317289.0", from a spreadsheet/pandas import
    # step somewhere in the pipeline) instead of a plain digit string. Phone
    # numbers are never legitimately fractional, so trimming a trailing ".0" is
    # safe here -- this is a display-layer fix, the DB row itself still needs a
    # proper cleanup pass.
    if value and re.fullmatch(r'\d+\.0', value):
        return value[:-2]
    return value


def tel_href(value):
    # DB numbers are domestic-format ("086 311 0668"); tel: links need E.164
    # so the number dials correctly regardless of the device's home region.
    digits = re.sub(r'\D', '', value or '')
    if not digits:
        return ''
    if digits.startswith('353'):
        return f'+{digits}'
    if digits.startswith('0'):
        return f'+353{digits[1:]}'
    return f'+{digits}'


def format_price(row):
    if row.get('price_amount') is None:
        return ''
    basis = f" {row['pricing_basis'].lower()}" if row.get('pricing_basis') else ''
    currency = row.get('price_currency') or 'EUR'
    return f"{currency} {row['price_amount']}{basis}"


def detail_rows_html(row):
    rows = []

    schedule = format_schedule(row)
    if schedule:
        rows.append(f'<div class="detail-row"><strong>Schedule:</strong> {schedule}</div>')

    if row.get('age_range_display'):
        rows.append(f'<div class="detail-row"><strong>Ages:</strong> {esc(row["age_range_display"])}</div>')

    if row.get('parental_requirement'):
        rows.append(f'<div class="detail-row"><strong>Supervision:</strong> {esc(row["parental_requirement"])}</div>')

    price = format_price(row)
    if price:
        rows.append(f'<div class="detail-row"><strong>Price:</strong> {esc(price)}</div>')
    if row.get('pricing_details'):
        rows.append(f'<div class="detail-row">{esc(row["pricing_details"])}</div>')

    class_types = row.get('class_types')
    if isinstance(class_types, list) and class_types:
        rows.append(f'<div class="detail-row"><strong>Class types:</strong> {esc(", ".join(class_types))}</div>')

    contact_parts = []
    if row.get('phone_number'):
        phone_display = esc(format_phone(row['phone_number']))
        href = tel_href(row['phone_number'])
        contact_parts.append(f'<a href="tel:{href}">{phone_display}</a>' if href else phone_display)
    if row.get('email_address'):
        email = esc(row['email_address'])
        contact_parts.append(f'<a href="mailto:{email}">{email}</a>')
    if contact_parts:
        rows.append(f'<div class="detail-row"><strong>Contact:</strong> {" &middot; ".join(contact_parts)}</div>')

    facilities = row.get('facilities')
    if isinstance(facilities, list) and facilities:
        chips = ''.join(f'<span class="facility-chip">{esc(f)}</span>' for f in facilities)
        rows.append(f'<div class="detail-row"><strong>Facilities:</strong><br>{chips}</div>')

    if row.get('booking_url') and row.get('booking_url') != row.get('website_url'):
        rows.append(f'<div class="detail-row"><a href="{esc(row["booking_url"])}" target="_blank" rel="noopener">Booking page &rarr;</a></div>')

    verified = ''
    if row.get('date_verified'):
        check_icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><path d="M20 6L9 17l-5-5"/></svg>'
        verified = f'<div class="verified-badge">{check_icon} Verified {esc(row["date_verified"])}</div>'

    return verified + ''.join(rows)


def image_html(row):
    # Business pages live one level below repo root (business/*.html), so the
    # repo-root-relative paths stored in the DB need a "../" prefix here --
    # index.html (at the root) uses the same paths unprefixed.
    alt = esc(row.get('company_name'))
    banner = ''
    if row.get('hosted_image_path'):
        banner = f'<img class="banner-img" src="../{esc(row["hosted_image_path"])}" alt="{alt}" loading="lazy" onerror="this.remove()">'
    logo = ''
    if row.get('logo_path'):
        logo = f'<img class="logo-badge" src="../{esc(row["logo_path"])}" alt="{alt} logo" loading="lazy" onerror="this.remove()">'
    return banner + logo


def meta_description(row):
    desc = (row.get('description') or '').strip()
    if not desc:
        cat = row.get('category') or 'Kids classes'
        addr = row.get('address') or 'Ireland'
        desc = f"{row.get('company_name')} -- {cat} classes at {addr}. Find schedule, pricing and contact details."
    if len(desc) > 160:
        desc = desc[:157].rsplit(' ', 1)[0] + '...'
    return desc


def json_ld(row, slug):
    ld = {
        '@context': 'https://schema.org',
        '@type': 'LocalBusiness',
        'name': row.get('company_name'),
        'url': f'{SITE_URL}/business/{slug}.html',
    }
    if row.get('description'):
        ld['description'] = row['description']
    image_path = row.get('hosted_image_path') or row.get('logo_path')
    if image_path:
        ld['image'] = f'{SITE_URL}/{image_path}'
    if row.get('phone_number'):
        ld['telephone'] = tel_href(row['phone_number']) or format_phone(row['phone_number'])
    if row.get('email_address'):
        ld['email'] = row['email_address']
    if row.get('address'):
        addr = {'@type': 'PostalAddress', 'streetAddress': row['address'], 'addressCountry': 'IE'}
        if row.get('eircode'):
            addr['postalCode'] = row['eircode']
        ld['address'] = addr
    if row.get('latitude') is not None and row.get('longitude') is not None:
        ld['geo'] = {'@type': 'GeoCoordinates', 'latitude': row['latitude'], 'longitude': row['longitude']}

    offer = {}
    if row.get('price_amount') is not None:
        offer['price'] = row['price_amount']
        offer['priceCurrency'] = row.get('price_currency') or 'EUR'
    class_types = row.get('class_types')
    course_name_bits = [b for b in [row.get('category'), ', '.join(class_types) if isinstance(class_types, list) and class_types else None] if b]
    course = {
        '@type': 'Course',
        'name': ' — '.join(course_name_bits) or row.get('company_name'),
        'provider': {'@type': 'Organization', 'name': row.get('company_name')},
    }
    if row.get('description'):
        course['description'] = row['description']
    audience = {}
    if row.get('minimum_age') is not None:
        audience['suggestedMinAge'] = row['minimum_age']
    if row.get('maximum_age') is not None:
        audience['suggestedMaxAge'] = row['maximum_age']
    if audience:
        course['audience'] = {'@type': 'PeopleAudience', **audience}
    offer['itemOffered'] = course
    ld['makesOffer'] = {'@type': 'Offer', **offer}

    return json.dumps(ld, ensure_ascii=False).replace('</', '<\\/')


def map_section(row):
    lat, lon = row.get('latitude'), row.get('longitude')
    maps_link = f'https://www.google.com/maps/search/?api=1&query={quote(row.get("address") or row.get("company_name") or "")}'
    section = (
        '<div class="business-address">'
        f'<strong>Address:</strong> {esc(row.get("address") or "Contact for details")}<br>'
        f'<a href="{maps_link}" target="_blank" rel="noopener">View on Google Maps &rarr;</a>'
        '</div>'
    )
    if lat is not None and lon is not None:
        section += f'<div id="business-map" class="business-map" data-lat="{lat}" data-lon="{lon}"></div>'
    return section


def share_widget_html(row, canonical):
    share_title = esc(row.get('company_name'))
    whatsapp_icon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M20.5 3.5A11 11 0 003.4 17.4L2 22l4.7-1.4A11 11 0 1020.5 3.5zm-8.5 17a9 9 0 01-4.6-1.3l-.3-.2-3 .9.9-2.9-.2-.3A9 9 0 1112 20.5zm4.9-6.6c-.3-.1-1.6-.8-1.8-.9-.2-.1-.4-.1-.6.1-.2.3-.7.9-.8 1-.1.2-.3.2-.6.1-.3-.1-1.2-.4-2.2-1.4-.8-.7-1.4-1.6-1.5-1.9-.2-.3 0-.5.1-.6.1-.1.3-.3.4-.5.1-.1.2-.3.3-.4.1-.2 0-.4 0-.5 0-.1-.6-1.5-.8-2-.2-.5-.4-.4-.6-.4h-.5c-.2 0-.5.1-.7.3-.2.3-1 1-1 2.3 0 1.4 1 2.7 1.1 2.9.1.2 2 3.1 4.9 4.3.7.3 1.2.5 1.6.6.7.2 1.3.2 1.8.1.5-.1 1.6-.6 1.8-1.3.2-.6.2-1.2.2-1.3-.1-.1-.3-.2-.5-.3z"/></svg>'
    email_icon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 6l-10 7L2 6"/></svg>'
    copy_icon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>'
    share_icon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.6" y1="10.6" x2="15.4" y2="6.4"/><line x1="8.6" y1="13.4" x2="15.4" y2="17.6"/></svg>'
    return f'''<div class="share-wrap">
                        <button type="button" class="share-toggle" aria-haspopup="true" aria-expanded="false">{share_icon} Share</button>
                        <div class="share-menu" hidden data-title="{share_title}" data-url="{canonical}">
                            <a class="share-option" data-share="whatsapp" href="#" target="_blank" rel="noopener">{whatsapp_icon} WhatsApp</a>
                            <a class="share-option" data-share="email" href="#">{email_icon} Email</a>
                            <button type="button" class="share-option" data-share="copy">{copy_icon} <span class="share-copy-label">Copy link</span></button>
                        </div>
                    </div>'''


def render_page(row, slug):
    company = esc(row.get('company_name'))
    category = row.get('category') or 'Class'
    title = f"{row.get('company_name')} — {category} classes | Kids Patch"
    desc = meta_description(row)
    canonical = f'{SITE_URL}/business/{slug}.html'
    cat_link = f'../index.html?cat={quote(row.get("category") or "")}'

    image_path = row.get('hosted_image_path') or row.get('logo_path')
    og_image_url = f'{SITE_URL}/{image_path}' if image_path else f'{SITE_URL}/og-image.png'
    og_image = f'<meta property="og:image" content="{og_image_url}">\n    <meta name="twitter:image" content="{og_image_url}">'

    dropoff_tag = ''
    if row.get('parental_requirement') == 'Drop-off':
        dropoff_tag = '<span class="tag" style="background:#dcfce7; color:#166534;">Drop-off</span>'

    map_script = ''
    if row.get('latitude') is not None and row.get('longitude') is not None:
        map_script = f'''
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
    <script>
        const mapEl = document.getElementById('business-map');
        if (mapEl) {{
            const m = L.map('business-map').setView([{row["latitude"]}, {row["longitude"]}], 15);
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19, attribution: '&copy; OpenStreetMap' }}).addTo(m);
            L.marker([{row["latitude"]}, {row["longitude"]}]).addTo(m);
        }}
    </script>'''

    leaflet_css = ''
    if row.get('latitude') is not None and row.get('longitude') is not None:
        leaflet_css = '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin=""/>\n    '

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
    <meta name="description" content="{esc(desc)}">
    <link rel="canonical" href="{canonical}">
    <meta property="og:title" content="{esc(title)}">
    <meta property="og:description" content="{esc(desc)}">
    <meta property="og:type" content="business.business">
    <meta property="og:url" content="{canonical}">
    {og_image}
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{esc(title)}">
    <meta name="twitter:description" content="{esc(desc)}">
    {leaflet_css}<link rel="stylesheet" href="../styles.css">
    <script src="../share.js" defer></script>
    <script type="application/ld+json">{json_ld(row, slug)}</script>
</head>
<body>
    <div class="business-page">
        <a href="../index.html" class="brand-logo" style="display:inline-block;">Kids Patch</a>
        <nav class="breadcrumb">
            <a href="../index.html">Home</a> &rsaquo; <a href="{cat_link}">{esc(category)}</a> &rsaquo; {company}
        </nav>
        <main class="business-main">
            <div class="business-card">
                <div class="card-image">{image_html(row)}</div>
                <div class="card-content">
                    <h1>{company}</h1>
                    <div class="tag-container">
                        <span class="tag">{esc(category)}</span>
                        {dropoff_tag}
                    </div>
                    <p class="description" style="-webkit-line-clamp: unset;">{esc(row.get("description")) or 'No description available.'}</p>
                    {detail_rows_html(row)}
                    {map_section(row)}
                    <a href="{esc(row.get("website_url")) or "#"}" target="_blank" rel="noopener" class="button">Visit Website</a>
                    {share_widget_html(row, canonical)}
                </div>
            </div>
            <div class="business-backlinks">
                <a href="../index.html">&larr; Back to full directory</a>
                <a href="{cat_link}">More {esc(category)} classes &rarr;</a>
            </div>
        </main>
    </div>
{map_script}
</body>
</html>'''


def self_validate_json_ld(page_html, slug):
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', page_html, re.DOTALL)
    if not match:
        raise ValueError(f'{slug}: no JSON-LD block found')
    try:
        json.loads(match.group(1).replace('<\\/', '</'))
    except json.JSONDecodeError as e:
        raise ValueError(f'{slug}: invalid JSON-LD ({e})')


def build_sitemap(slugs):
    today = date.today().isoformat()
    urls = [f'  <url>\n    <loc>{SITE_URL}/</loc>\n    <lastmod>{today}</lastmod>\n  </url>']
    for slug in slugs:
        urls.append(f'  <url>\n    <loc>{SITE_URL}/business/{slug}.html</loc>\n    <lastmod>{today}</lastmod>\n  </url>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + '\n'.join(urls) +
        '\n</urlset>\n'
    )


def main():
    print('Fetching rows from Supabase...')
    rows = fetch_all_rows()
    print(f'Fetched {len(rows)} rows.')

    BUSINESS_DIR.mkdir(exist_ok=True)

    manifest = {}
    slugs = []
    for row in rows:
        if not row.get('company_name') or row.get('id') is None:
            continue
        slug = make_slug(row)
        page_html = render_page(row, slug)
        self_validate_json_ld(page_html, slug)
        (BUSINESS_DIR / f'{slug}.html').write_text(page_html, encoding='utf-8')
        manifest[str(row['id'])] = f'business/{slug}.html'
        slugs.append(slug)

    (REPO_ROOT / 'sitemap.xml').write_text(build_sitemap(slugs), encoding='utf-8')
    (REPO_ROOT / 'business-index.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    print(f'Wrote {len(slugs)} business pages, sitemap.xml, business-index.json.')


if __name__ == '__main__':
    main()
