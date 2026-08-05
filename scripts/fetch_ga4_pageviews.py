"""Pulls trailing-30-day pageviews per business page out of GA4 and writes them
into classes.page_views_30d, so portal.html can show each owner how many
people viewed their listing. Read-only against GA4, read+write against
Supabase (needs the service-role key, unlike the anon-key scripts elsewhere
in this repo, since RLS only grants SELECT to anon).

Auth to GA4 is via Workload Identity Federation, not a downloaded service
account key -- our Google Workspace org has a policy blocking service account
key creation, so the GitHub Actions workflow (.github/workflows/
fetch-ga4-pageviews.yml) mints a short-lived OIDC-derived access token via
google-github-actions/auth and hands it to this script as GA4_ACCESS_TOKEN.
That's also why this makes a plain REST call instead of using the
google-analytics-data client library -- no Google client libraries are
installed anywhere else in this repo (see generate_business_pages.py,
scrape_social_links_safe.py -- both stdlib-only urllib), so a raw request
avoids a one-off dependency for a single API call.

Run locally: GA4_ACCESS_TOKEN=$(gcloud auth print-access-token \
  --impersonate-service-account=ga4-reader@kidspatch-analytics.iam.gserviceaccount.com) \
  SB_SECRET=$(cat ~/Documents/kidspatch_secret.txt) python3 scripts/fetch_ga4_pageviews.py
Also run nightly by .github/workflows/fetch-ga4-pageviews.yml.
"""

import json
import os
import re
import urllib.error
import urllib.request

SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co'
GA4_PROPERTY_ID = '548070713'
PAGE_ID_RE = re.compile(r'-(\d+)\.html$')


def fetch_ga4_pageviews(access_token):
    """Returns {business_id: view_count} for every /business/*.html path GA4
    has data for in the trailing 30 days."""
    body = {
        'dateRanges': [{'startDate': '30daysAgo', 'endDate': 'today'}],
        'dimensions': [{'name': 'pagePath'}],
        'metrics': [{'name': 'screenPageViews'}],
        'dimensionFilter': {
            'filter': {
                'fieldName': 'pagePath',
                'stringFilter': {'matchType': 'BEGINS_WITH', 'value': '/business/'},
            }
        },
        'limit': 100000,
    }
    req = urllib.request.Request(
        f'https://analyticsdata.googleapis.com/v1beta/properties/{GA4_PROPERTY_ID}:runReport',
        data=json.dumps(body).encode(),
        headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        report = json.loads(resp.read())

    counts = {}
    for row in report.get('rows', []):
        page_path = row['dimensionValues'][0]['value']
        views = int(row['metricValues'][0]['value'])
        match = PAGE_ID_RE.search(page_path)
        if not match:
            continue
        business_id = int(match.group(1))
        # A business page can show up under more than one pagePath (query
        # strings, trailing slash variants GA didn't normalize) -- sum them
        # rather than overwrite, so nothing is silently dropped.
        counts[business_id] = counts.get(business_id, 0) + views
    return counts


def fetch_all_business_ids(secret):
    # PostgREST caps an unpaginated response at 1000 rows -- there are ~1800
    # businesses, so this must page via Range headers (same pattern as
    # fetch_all_rows() in generate_business_pages.py) or several hundred rows
    # silently never get a page_views_30d value written.
    headers = {'apikey': secret, 'Authorization': f'Bearer {secret}'}
    ids, offset, page = set(), 0, 1000
    while True:
        req = urllib.request.Request(
            f'{SUPABASE_URL}/rest/v1/classes?select=id&order=id',
            headers={**headers, 'Range-Unit': 'items', 'Range': f'{offset}-{offset + page - 1}'},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.loads(resp.read())
        ids.update(row['id'] for row in batch)
        if len(batch) < page:
            return ids
        offset += page


def write_pageviews(secret, counts, all_ids):
    # Every business row needs an explicit value each run, not just the ones
    # GA4 returned -- a page that had views last week but none in the current
    # trailing-30-day window must drop back to 0, not keep showing a stale
    # number forever.
    headers = {
        'apikey': secret, 'Authorization': f'Bearer {secret}',
        'Content-Type': 'application/json', 'Prefer': 'return=minimal',
    }
    updated = 0
    for business_id in all_ids:
        views = counts.get(business_id, 0)
        req = urllib.request.Request(
            f'{SUPABASE_URL}/rest/v1/classes?id=eq.{business_id}',
            data=json.dumps({'page_views_30d': views}).encode(),
            headers=headers, method='PATCH',
        )
        with urllib.request.urlopen(req, timeout=20):
            pass
        updated += 1
    return updated


def main():
    access_token = os.environ['GA4_ACCESS_TOKEN']
    secret = os.environ['SB_SECRET']

    print('Fetching GA4 pageviews for /business/ paths (trailing 30 days)...')
    counts = fetch_ga4_pageviews(access_token)
    print(f'GA4 returned data for {len(counts)} business pages.')

    all_ids = fetch_all_business_ids(secret)
    updated = write_pageviews(secret, counts, all_ids)
    print(f'Updated page_views_30d for {updated} rows.')


if __name__ == '__main__':
    main()
