"""Generates the blog: one static page per published row in `blog_posts`
(blog/<slug>.html), plus the blog/index.html listing page, and merges those
URLs into the already-written sitemap.xml.

Must run AFTER generate_landing_pages.py in the same checkout -- it's the
one that (re)writes sitemap.xml from scratch, and this script only ever
appends/refreshes its own /blog/ entries in that file rather than rebuilding
it (see merge_sitemap()), so nothing here needs to know about business or
landing page URLs directly.

Requires the `markdown` package (see requirements.txt) -- the one exception
to every other script in this repo being stdlib-only, since hand-rolling a
Markdown parser isn't worth the risk for real editorial content.

Run locally (after the other two): python3 scripts/generate_blog_pages.py
Also run by .github/workflows/build-business-pages.yml.
"""

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from urllib.parse import quote

import markdown

from generate_business_pages import (
    esc, file_version, self_validate_json_ld, REPO_ROOT, SITE_URL,
    STYLES_VERSION, ANALYTICS_JS_VERSION, SITE_HEADER_HTML, SITE_FOOTER_HTML,
    SUPABASE_URL, SUPABASE_ANON_KEY,
)

BLOG_DIR = REPO_ROOT / 'blog'


def fetch_published_posts():
    # Mirrors fetch_all_rows()'s Range-header pagination (see that function's
    # comment in generate_business_pages.py / the Supabase PostgREST gotcha
    # it guards against) -- post counts won't be anywhere near 1000 for a
    # long time, but paginating unconditionally costs nothing and avoids the
    # silent 1000-row cap if this ever changes.
    headers = {'apikey': SUPABASE_ANON_KEY, 'Authorization': f'Bearer {SUPABASE_ANON_KEY}'}
    now_iso = datetime.now(timezone.utc).isoformat()
    rows, offset, page = [], 0, 1000
    while True:
        req = urllib.request.Request(
            f'{SUPABASE_URL}/rest/v1/blog_posts?select=*'
            f'&status=eq.published&published_at=lte.{quote(now_iso)}'
            '&order=published_at.desc',
            headers={**headers, 'Range-Unit': 'items', 'Range': f'{offset}-{offset + page - 1}'},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.loads(resp.read())
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows


def format_post_date(published_at):
    if not published_at:
        return ''
    try:
        # Supabase timestamps end in 'Z' or a numeric offset; fromisoformat
        # (on the Python versions this runs under) wants '+00:00', not 'Z'.
        dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
        return dt.strftime('%d %B %Y')
    except (ValueError, AttributeError):
        return ''


def meta_description(post):
    desc = (post.get('meta_description') or post.get('excerpt') or '').strip()
    if len(desc) > 160:
        desc = desc[:157].rsplit(' ', 1)[0] + '...'
    return desc


def json_ld(post, canonical):
    ld = {
        '@context': 'https://schema.org',
        '@type': 'BlogPosting',
        'headline': post.get('title'),
        'url': canonical,
        'author': {'@type': 'Organization', 'name': post.get('author_name') or 'Kids Patch Team'},
        'publisher': {
            '@type': 'Organization',
            'name': 'Kids Patch',
            'logo': {'@type': 'ImageObject', 'url': f'{SITE_URL}/apple-touch-icon.png'},
        },
    }
    if post.get('published_at'):
        ld['datePublished'] = post['published_at']
    if post.get('excerpt'):
        ld['description'] = post['excerpt']
    if post.get('featured_image_path'):
        ld['image'] = post['featured_image_path']
    return json.dumps(ld, ensure_ascii=False).replace('</', '<\\/')


def blog_card_html(post):
    # Reuses .landing-card / .card-image / .banner-img verbatim (see
    # landing_card_html() in generate_landing_pages.py and .card-image
    # .banner-img in styles.css) -- no new CSS needed for the grid itself.
    title = esc(post.get('title'))
    date_str = esc(format_post_date(post.get('published_at')))
    image = ''
    if post.get('featured_image_path'):
        image = f'<img class="banner-img" src="{esc(post["featured_image_path"])}" alt="{title}" loading="lazy" onerror="this.remove()">'
    return f'''<div class="landing-card">
        <div class="card-image">{image}</div>
        <div class="card-content">
            <h3>{title}</h3>
            <div class="landing-card-meta">{date_str}</div>
            <p class="description">{esc(post.get("excerpt") or "")}</p>
            <a href="{esc(post['slug'])}.html" class="button">Read more &rarr;</a>
        </div>
    </div>'''


def render_post_page(post):
    slug = post['slug']
    title = f"{post['title']} | Kids Patch Blog"
    desc = meta_description(post)
    canonical = f'{SITE_URL}/blog/{slug}.html'
    date_str = format_post_date(post.get('published_at'))
    author = post.get('author_name') or 'Kids Patch Team'

    # content_markdown is admin-authored only (RLS restricts writes to
    # admins.html's Blog tab), so the rendered HTML is trusted output, same
    # trust boundary as every other admin-entered field on the site -- unlike
    # the enquiry/claim forms, there's no public-submission path into this
    # table at all.
    content_html = markdown.markdown(post.get('content_markdown') or '', extensions=['extra'])

    # featured_image_path is always a full https:// Supabase Storage public
    # URL (set via getPublicUrl() in admin.html's upload widget), never a
    # repo-relative path -- unlike hosted_image_path/logo_path on `classes`,
    # which are relative and need the "../" prefix image_html() adds. Used
    # as-is here.
    og_image = post.get('featured_image_path') or f'{SITE_URL}/og-image.png'
    featured_img_html = ''
    if post.get('featured_image_path'):
        featured_img_html = f'<img class="blog-post-hero" src="{esc(post["featured_image_path"])}" alt="{esc(post["title"])}" loading="lazy">'

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
    <meta property="og:title" content="{esc(post['title'])}">
    <meta property="og:description" content="{esc(desc)}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{canonical}">
    <meta property="og:image" content="{esc(og_image)}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{esc(post['title'])}">
    <meta name="twitter:description" content="{esc(desc)}">
    <link rel="stylesheet" href="../styles.css?v={STYLES_VERSION}">
    <script src="../analytics.js?v={ANALYTICS_JS_VERSION}" defer></script>
    <script type="application/ld+json">{json_ld(post, canonical)}</script>
</head>
<body>
{SITE_HEADER_HTML}
    <div class="blog-post-page">
        <nav class="breadcrumb">
            <a href="../index.html">Home</a> &rsaquo; <a href="index.html">Blog</a> &rsaquo; {esc(post['title'])}
        </nav>
        <article>
            <h1>{esc(post['title'])}</h1>
            <div class="blog-post-meta">By {esc(author)} &middot; {esc(date_str)}</div>
            {featured_img_html}
            <div class="blog-post-body">{content_html}</div>
        </article>
        <div class="business-backlinks">
            <a href="index.html">&larr; Back to the blog</a>
        </div>
    </div>
{SITE_FOOTER_HTML}
</body>
</html>'''


def render_index_page(posts):
    title = 'Blog | Kids Patch'
    desc = "Tips, guides and news for parents finding kids' classes and activities across Ireland."
    canonical = f'{SITE_URL}/blog/index.html'
    cards_html = ''.join(blog_card_html(p) for p in posts) or '<p class="no-results">No posts published yet &mdash; check back soon.</p>'

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
    <meta property="og:type" content="website">
    <meta property="og:url" content="{canonical}">
    <meta property="og:image" content="{SITE_URL}/og-image.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{esc(title)}">
    <meta name="twitter:description" content="{esc(desc)}">
    <link rel="stylesheet" href="../styles.css?v={STYLES_VERSION}">
    <script src="../analytics.js?v={ANALYTICS_JS_VERSION}" defer></script>
</head>
<body>
{SITE_HEADER_HTML}
    <div class="landing-page">
        <nav class="breadcrumb">
            <a href="../index.html">Home</a> &rsaquo; Blog
        </nav>
        <h1>Kids Patch Blog</h1>
        <p>{esc(desc)}</p>
        <div class="landing-grid">{cards_html}</div>
    </div>
{SITE_FOOTER_HTML}
</body>
</html>'''


def merge_sitemap(blog_paths):
    # Idempotent merge: drop any /blog/ entries left over from a previous
    # run (a post may since have been unpublished, deleted, or re-slugged),
    # then append the current set of published blog URLs with a fresh
    # lastmod. Never touches business/ or classes/ entries -- this script
    # only ever owns its own URLs in this file.
    sitemap_path = REPO_ROOT / 'sitemap.xml'
    existing_urls = re.findall(r'<loc>(.*?)</loc>', sitemap_path.read_text(encoding='utf-8'))
    kept_urls = [u for u in existing_urls if '/blog/' not in u]
    blog_urls = [f'{SITE_URL}/{path}' for path in blog_paths]
    all_urls = kept_urls + blog_urls

    today = date.today().isoformat()
    urls_xml = '\n'.join(
        f'  <url>\n    <loc>{u}</loc>\n    <lastmod>{today}</lastmod>\n  </url>' for u in all_urls
    )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{urls_xml}\n</urlset>\n'
    )
    sitemap_path.write_text(sitemap, encoding='utf-8')
    return len(all_urls)


def main():
    print('Fetching published blog posts from Supabase...')
    try:
        posts = fetch_published_posts()
    except urllib.error.HTTPError as e:
        # 404 here means blog_posts doesn't exist yet -- add_blog_posts_table.sql
        # hasn't been run in Supabase yet. This step runs unconditionally on
        # every scheduled workflow run (see build-business-pages.yml), so it
        # must exit cleanly rather than raise: a raised exception would fail
        # the whole job and skip the "Commit generated files" step, silently
        # breaking nightly business/landing page regeneration too until the
        # migration is applied. Any other HTTP error still raises normally.
        if e.code == 404:
            print(f'blog_posts table not found ({e}) -- skipping blog generation. '
                  'Run add_blog_posts_table.sql in the Supabase SQL editor to enable it.')
            sys.exit(0)
        raise
    print(f'Fetched {len(posts)} published posts.')

    BLOG_DIR.mkdir(exist_ok=True)

    manifest = {}
    blog_paths = []
    for post in posts:
        if not post.get('slug') or not post.get('title'):
            continue
        slug = post['slug']
        page_html = render_post_page(post)
        self_validate_json_ld(page_html, slug)
        (BLOG_DIR / f'{slug}.html').write_text(page_html, encoding='utf-8')
        manifest[str(post['id'])] = f'blog/{slug}.html'
        blog_paths.append(f'blog/{slug}.html')

    (BLOG_DIR / 'index.html').write_text(render_index_page(posts), encoding='utf-8')
    blog_paths.append('blog/index.html')

    (REPO_ROOT / 'blog-index.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    total_urls = merge_sitemap(blog_paths)
    print(f'Wrote {len(blog_paths) - 1} blog post pages + index. Merged sitemap.xml now has {total_urls} URLs.')


if __name__ == '__main__':
    main()
