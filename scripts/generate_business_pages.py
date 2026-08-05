"""Generates one static, crawlable HTML page per row in the `classes` table,
plus sitemap.xml and business-index.json (the slug manifest index.html links
to). Read-only against Supabase -- uses the public anon key, same one already
shipped in plaintext in index.html/portal.html (RLS restricts it to SELECT).

Run locally any time: python3 scripts/generate_business_pages.py
Also run nightly + on push by .github/workflows/build-business-pages.yml.
"""

import hashlib
import html
import json
import re
import urllib.error
import urllib.request
from datetime import date, timezone
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co'
SUPABASE_ANON_KEY = 'sb_publishable_eduvbMySPxHPT0iZjE_LqQ_w6nyjnjY'
SITE_URL = 'https://www.kidspatch.ie'

REPO_ROOT = Path(__file__).resolve().parent.parent
BUSINESS_DIR = REPO_ROOT / 'business'


def file_version(relative_path):
    """Short content hash for cache-busting a shared static asset (styles.css,
    share.js, landing-map.js) referenced with a relative ../ path from every
    generated page. Without this, a browser can cache one of these files
    indefinitely and keep showing stale styling/behaviour after a deploy --
    real bug, hit in practice (see LEARNINGS.md, 2026-08-04). index.html
    already did this by hand (styles.css?v=4); this makes it automatic and
    covers the generated pages too, which previously had no cache-busting
    at all.
    """
    path = REPO_ROOT / relative_path
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:10]


STYLES_VERSION = file_version('styles.css')
SHARE_JS_VERSION = file_version('share.js')
ANALYTICS_JS_VERSION = file_version('analytics.js')
NOTIFY_JS_VERSION = file_version('notify.js')
CLAIM_JS_VERSION = file_version('claim.js')

# Same sticky top nav and footer as index.html's -- generated pages (business + landing)
# previously used a bare ".brand-logo" text link with no icon, nav, or footer, left over
# from an older homepage design. Every generated page lives one directory down from the
# repo root (business/*.html, classes/*.html), same as index.html's own header/footer,
# so the "../" links below work unchanged everywhere this is used.
SITE_HEADER_HTML = '''    <header class="site-header">
        <div class="site-header-inner">
            <a href="../index.html" class="logo">
                <svg width="30" height="30" viewBox="0 0 40 40" fill="none" aria-hidden="true">
                    <path d="M20 2 L26 6 L34 6 L34 14 L38 20 L34 26 L34 34 L26 34 L20 38 L14 34 L6 34 L6 26 L2 20 L6 14 L6 6 L14 6 Z" fill="#0F6E6E"/>
                    <circle cx="20" cy="20" r="8" fill="#FFC857"/>
                </svg>
                Kids Patch
            </a>
            <nav class="site-nav">
                <a href="../index.html">Browse activities</a>
                <a href="../classes/index.html">Categories</a>
                <a href="../contact.html">Contact</a>
            </nav>
            <a href="../portal.html" class="btn-ghost">Manage your listing</a>
        </div>
    </header>'''

SITE_FOOTER_HTML = '''    <footer class="site-footer">
        <div class="site-footer-inner">
            <div class="logo">
                <svg viewBox="0 0 40 40" fill="none" width="26" height="26" aria-hidden="true">
                    <path d="M20 2 L26 6 L34 6 L34 14 L38 20 L34 26 L34 34 L26 34 L20 38 L14 34 L6 34 L6 26 L2 20 L6 14 L6 6 L14 6 Z" fill="#FAF9F6"/>
                    <circle cx="20" cy="20" r="8" fill="#FFC857"/>
                </svg>
                Kids Patch
            </div>
            <div class="site-footer-links">
                <a href="../classes/index.html">Browse all activities by category &amp; county</a>
                <a href="../portal.html">Business owner? Manage your listing</a>
                <a href="../contact.html">Contact us</a>
            </div>
        </div>
    </footer>'''


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


def with_utm(url, medium='referral'):
    # Tags outbound links (Visit Website, booking page) so a business owner
    # can see in their own analytics that a click came from Kids Patch --
    # separate from (and complementary to) the outbound_click GA event fired
    # alongside it via track_onclick().
    if not url:
        return url
    try:
        parts = urlsplit(url if '://' in url else f'https://{url}')
        query = dict(parse_qsl(parts.query))
        query['utm_source'] = 'kidspatch'
        query['utm_medium'] = medium
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    except ValueError:
        return url


def track_onclick(event_name, **params):
    # A static generated page has no post-load init step to wire up listeners
    # against, so click tracking here is a plain inline onclick -- htmlescaped
    # (via esc(), same helper as everywhere else in this file) rather than
    # trusted as-is, since company_name/category are free-text DB fields that
    # can contain quotes. json.dumps produces valid JS literal syntax for both
    # the event name and the params object.
    js = f'trackEvent({json.dumps(event_name)}, {json.dumps(params, ensure_ascii=False)})'
    return f'onclick="{esc(js)}"'


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
        phone_track = track_onclick('phone_click', business_id=row.get('id'), business_name=row.get('company_name'))
        contact_parts.append(f'<a href="tel:{href}" {phone_track}>{phone_display}</a>' if href else phone_display)
    if row.get('email_address'):
        email = esc(row['email_address'])
        email_track = track_onclick('email_click', business_id=row.get('id'), business_name=row.get('company_name'))
        contact_parts.append(f'<a href="mailto:{email}" {email_track}>{email}</a>')
    if contact_parts:
        rows.append(f'<div class="detail-row"><strong>Contact:</strong> {" &middot; ".join(contact_parts)}</div>')

    facilities = row.get('facilities')
    if isinstance(facilities, list) and facilities:
        chips = ''.join(f'<span class="facility-chip">{esc(f)}</span>' for f in facilities)
        rows.append(f'<div class="detail-row"><strong>Facilities:</strong><br>{chips}</div>')

    if row.get('booking_url') and row.get('booking_url') != row.get('website_url'):
        booking_href = esc(with_utm(row['booking_url'], 'referral'))
        booking_track = track_onclick('outbound_click', business_id=row.get('id'), business_name=row.get('company_name'), category=row.get('category'), link_type='booking')
        rows.append(f'<div class="detail-row"><a href="{booking_href}" target="_blank" rel="noopener" {booking_track}>Booking page &rarr;</a></div>')

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
    directions_track = track_onclick('directions_click', business_id=row.get('id'), business_name=row.get('company_name'))
    section = (
        '<div class="business-address">'
        f'<strong>Address:</strong> {esc(row.get("address") or "Contact for details")}<br>'
        f'<a href="{maps_link}" target="_blank" rel="noopener" {directions_track}>View on Google Maps &rarr;</a>'
        '</div>'
    )
    if lat is not None and lon is not None:
        section += f'<div id="business-map" class="business-map" data-lat="{lat}" data-lon="{lon}"></div>'
    return section


def share_widget_html(row, canonical):
    share_title = esc(row.get('company_name'))
    whatsapp_icon = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.5 3.5A11 11 0 003.4 17.4L2 22l4.7-1.4A11 11 0 1020.5 3.5zm-8.5 17a9 9 0 01-4.6-1.3l-.3-.2-3 .9.9-2.9-.2-.3A9 9 0 1112 20.5zm4.9-6.6c-.3-.1-1.6-.8-1.8-.9-.2-.1-.4-.1-.6.1-.2.3-.7.9-.8 1-.1.2-.3.2-.6.1-.3-.1-1.2-.4-2.2-1.4-.8-.7-1.4-1.6-1.5-1.9-.2-.3 0-.5.1-.6.1-.1.3-.3.4-.5.1-.1.2-.3.3-.4.1-.2 0-.4 0-.5 0-.1-.6-1.5-.8-2-.2-.5-.4-.4-.6-.4h-.5c-.2 0-.5.1-.7.3-.2.3-1 1-1 2.3 0 1.4 1 2.7 1.1 2.9.1.2 2 3.1 4.9 4.3.7.3 1.2.5 1.6.6.7.2 1.3.2 1.8.1.5-.1 1.6-.6 1.8-1.3.2-.6.2-1.2.2-1.3-.1-.1-.3-.2-.5-.3z"/></svg>'
    facebook_icon = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M22 12.06C22 6.5 17.52 2 12 2S2 6.5 2 12.06C2 17.08 5.66 21.23 10.44 22v-7.03H7.9v-2.91h2.54V9.85c0-2.51 1.49-3.9 3.77-3.9 1.09 0 2.24.2 2.24.2v2.46h-1.26c-1.24 0-1.63.77-1.63 1.56v1.89h2.78l-.44 2.91h-2.34V22C18.34 21.23 22 17.08 22 12.06z"/></svg>'
    x_icon = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.9 2h3.2l-7 8 8.2 12h-6.4l-5-6.8L5.4 22H2.2l7.5-8.6L1.8 2h6.6l4.5 6.2L18.9 2zm-1.1 18h1.8L7.2 4H5.3l12.5 16z"/></svg>'
    email_icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 6l-10 7L2 6"/></svg>'
    copy_icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.5 13.5a4 4 0 005.66 0l3-3a4 4 0 00-5.66-5.66l-1.5 1.5"/><path d="M13.5 10.5a4 4 0 00-5.66 0l-3 3a4 4 0 005.66 5.66l1.5-1.5"/></svg>'
    return f'''<div class="share-row" data-title="{share_title}" data-url="{canonical}" data-business-id="{esc(row.get('id'))}">
                        <span class="share-label">Share:</span>
                        <a class="share-icon share-whatsapp" data-share="whatsapp" href="#" target="_blank" rel="noopener" aria-label="Share on WhatsApp" title="Share on WhatsApp">{whatsapp_icon}</a>
                        <a class="share-icon share-facebook" data-share="facebook" href="#" target="_blank" rel="noopener" aria-label="Share on Facebook" title="Share on Facebook">{facebook_icon}</a>
                        <a class="share-icon share-x" data-share="x" href="#" target="_blank" rel="noopener" aria-label="Share on X" title="Share on X">{x_icon}</a>
                        <a class="share-icon share-email" data-share="email" href="#" aria-label="Share by email" title="Share by email">{email_icon}</a>
                        <button type="button" class="share-icon share-copy" data-share="copy" aria-label="Copy link" title="Copy link">{copy_icon}<span class="copy-tooltip">Copied!</span></button>
                    </div>'''


def social_widget_html(row):
    # Only rendered when the DB actually has a facebook_url/instagram_url --
    # scripts/scrape_social_links_safe.py populates these, but most rows still
    # don't have one, so this must stay silent (return '') rather than show
    # empty/placeholder icons.
    facebook = row.get('facebook_url')
    instagram = row.get('instagram_url')
    if not facebook and not instagram:
        return ''
    facebook_icon = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M22 12.06C22 6.5 17.52 2 12 2S2 6.5 2 12.06C2 17.08 5.66 21.23 10.44 22v-7.03H7.9v-2.91h2.54V9.85c0-2.51 1.49-3.9 3.77-3.9 1.09 0 2.24.2 2.24.2v2.46h-1.26c-1.24 0-1.63.77-1.63 1.56v1.89h2.78l-.44 2.91h-2.34V22C18.34 21.23 22 17.08 22 12.06z"/></svg>'
    instagram_icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="5"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/></svg>'
    icons = []
    if facebook:
        href = esc(with_utm(facebook))
        track = track_onclick('outbound_click', business_id=row.get('id'), business_name=row.get('company_name'), category=row.get('category'), link_type='facebook')
        icons.append(f'<a class="social-icon social-facebook" href="{href}" target="_blank" rel="noopener" aria-label="Facebook page" title="Facebook" {track}>{facebook_icon}</a>')
    if instagram:
        href = esc(with_utm(instagram))
        track = track_onclick('outbound_click', business_id=row.get('id'), business_name=row.get('company_name'), category=row.get('category'), link_type='instagram')
        icons.append(f'<a class="social-icon social-instagram" href="{href}" target="_blank" rel="noopener" aria-label="Instagram page" title="Instagram" {track}>{instagram_icon}</a>')
    return f'<div class="social-row">{"".join(icons)}</div>'


def claim_button_html(row):
    # openClaimModal() (claim.js) is generic across index.html's dynamically
    # rendered cards and these static pages -- same function, same modal
    # markup (CLAIM_MODAL_HTML below), just invoked via onclick here instead
    # of a data-id/data-name pair read by a delegated listener, since a
    # static page has no per-card delegation infrastructure to hook into.
    onclick = f'window.openClaimModal({json.dumps(str(row.get("id")))}, {json.dumps(row.get("company_name"))})'
    return f'<button type="button" class="button claim-btn" onclick="{esc(onclick)}">Claim this business</button>'


# Same modal markup as index.html's #claim-modal -- claim.js is written against
# this exact structure (element IDs) regardless of which page includes it.
CLAIM_MODAL_HTML = '''<div id="claim-modal" class="modal-overlay">
        <div class="modal">
            <button id="close-modal" class="close-modal">&times;</button>
            <h3 id="modal-business-name">Claim Business</h3>
            <p>Verify your ownership to manage this page and update your details.</p>

            <div id="claim-loading" style="display:none; text-align:center; padding: 1rem 0; color: var(--text-muted);">Checking claim status&hellip;</div>

            <form id="claim-form" style="display:none;">
                <input type="hidden" id="claim-business-id">
                <input type="hidden" id="claim-business-title">
                <input type="text" id="claim-hp" name="website" tabindex="-1" autocomplete="off" aria-hidden="true" style="position:absolute; left:-9999px; width:1px; height:1px; opacity:0;">

                <div class="form-group">
                    <label for="claim-name">Your Full Name</label>
                    <input type="text" id="claim-name" required placeholder="e.g. Jane Doe">
                </div>
                <div class="form-group">
                    <label for="claim-email">Business Email Address</label>
                    <input type="email" id="claim-email" required placeholder="e.g. jane@yourbusiness.ie">
                    <small style="color:var(--text-muted); font-size: 0.75rem; display:block; margin-top:4px;">Must be an official business domain.</small>
                </div>
                <div class="form-group">
                    <label for="claim-position">Your Position / Role</label>
                    <input type="text" id="claim-position" required placeholder="e.g. Owner, Manager">
                </div>
                <button type="submit" class="submit-btn" id="claim-submit">Submit Claim Request</button>
            </form>

            <div id="claim-already" style="display:none; text-align:center; background:#fef3c7; color:#92400e; padding:1.5rem; border-radius:8px;"></div>

            <div id="claim-success" style="display: none; text-align: center; color: #166534; background: #dcfce7; padding: 1.5rem; border-radius: 8px;">
                <strong>Request Submitted!</strong><br>We'll review your details. Once approved, come back to <a href="../portal.html" style="color:#166534; font-weight:700;">Manage Your Listing</a> and log in with the email address you just gave us to edit your business.
            </div>
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
    <link rel="icon" href="/favicon.ico" sizes="any">
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="48x48" href="/favicon-48x48.png">
    <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
    <link rel="manifest" href="/site.webmanifest">
    <meta property="og:title" content="{esc(title)}">
    <meta property="og:description" content="{esc(desc)}">
    <meta property="og:type" content="business.business">
    <meta property="og:url" content="{canonical}">
    {og_image}
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{esc(title)}">
    <meta name="twitter:description" content="{esc(desc)}">
    {leaflet_css}<link rel="stylesheet" href="../styles.css?v={STYLES_VERSION}">
    <script src="../analytics.js?v={ANALYTICS_JS_VERSION}" defer></script>
    <script src="../share.js?v={SHARE_JS_VERSION}" defer></script>
    <script src="../notify.js?v={NOTIFY_JS_VERSION}" defer></script>
    <script src="../claim.js?v={CLAIM_JS_VERSION}" defer></script>
    <script type="application/ld+json">{json_ld(row, slug)}</script>
</head>
<body>
{SITE_HEADER_HTML}
    <div class="business-page">
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
                    {social_widget_html(row)}
                    {map_section(row)}
                    <a href="{esc(with_utm(row.get("website_url"))) or "#"}" target="_blank" rel="noopener" class="button" {track_onclick('outbound_click', business_id=row.get('id'), business_name=row.get('company_name'), category=row.get('category'), link_type='website')}>Visit Website</a>
                    {claim_button_html(row)}
                    {share_widget_html(row, canonical)}
                </div>
            </div>
            <div class="business-backlinks">
                <a href="../index.html" id="back-to-search-results" style="display:none;">&larr; Back to search results</a>
                <a href="../index.html">&larr; Back to full directory</a>
                <a href="{cat_link}">More {esc(category)} classes &rarr;</a>
            </div>
        </main>
    </div>
{SITE_FOOTER_HTML}
    {CLAIM_MODAL_HTML}
    <script>
        (function() {{
            // index.html stashes the query string of the visitor's last search in
            // sessionStorage (see kpLastSearch) since a plain link here can't know
            // it -- this page is static and pre-generated. Falls back to nothing
            // (link stays hidden) if the visitor arrived without ever searching,
            // e.g. from Google or a shared URL.
            try {{
                const saved = sessionStorage.getItem('kpLastSearch');
                if (saved) {{
                    const link = document.getElementById('back-to-search-results');
                    link.href = '../index.html?' + saved;
                    link.style.display = '';
                }}
            }} catch (e) {{}}
        }})();
    </script>
    <script>
        window.SUPABASE_URL = window.SUPABASE_URL || 'https://gnozodfteywsiwcnbwch.supabase.co';
        window.SUPABASE_ANON_KEY = window.SUPABASE_ANON_KEY || 'sb_publishable_eduvbMySPxHPT0iZjE_LqQ_w6nyjnjY';
    </script>
    <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
    <script>
        window.supabaseClient = window.supabase.createClient(window.SUPABASE_URL, window.SUPABASE_ANON_KEY);
    </script>
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
