import csv
import json
import re
import time
import urllib.parse
import urllib.request

SRC = '/Users/davidmacmahon/kids-class-directory-website/downloads/candidates_outside_dublin_not_yet_added.csv'
DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/candidates_outside_dublin_geocoded.csv'

# Whole island of Ireland, not just Dublin -- scope is Ireland-wide now.
LAT_MIN, LAT_MAX = 51.3, 55.5
LON_MIN, LON_MAX = -10.75, -5.9

HEADERS = {'User-Agent': 'kids-class-directory-geocoder/1.0 (davidmacmahon1@gmail.com)'}


def nominatim_query(q):
    url = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode({
        'q': q, 'format': 'json', 'limit': 1, 'countrycodes': 'ie',
    })
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    if not data:
        return None
    lat, lon = float(data[0]['lat']), float(data[0]['lon'])
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        return None
    return lat, lon


def address_variants(address):
    segs = [s.strip() for s in address.split(',') if s.strip()]
    variants = [address]
    if len(segs) > 1:
        variants.append(', '.join(segs[1:]))  # drop leading venue/building name
    if len(segs) > 2:
        variants.append(', '.join(segs[-2:]))  # area/county level only
    if len(segs) > 1:
        variants.append(segs[-1])  # last segment alone (often county/country)
    seen = set()
    out = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def main():
    rows = list(csv.DictReader(open(SRC)))
    cache = {}
    resolved = 0
    unresolved = 0

    for i, r in enumerate(rows):
        addr = r.get('address', '').strip()
        if addr in cache:
            lat, lon, method = cache[addr]
        else:
            lat = lon = None
            method = None
            for vi, variant in enumerate(address_variants(addr)):
                try:
                    result = nominatim_query(variant)
                except Exception as e:
                    result = None
                    print(f'  ERROR querying "{variant}": {e}')
                time.sleep(1.1)
                if result:
                    lat, lon = result
                    method = ['full', 'drop-venue', 'area-level', 'last-segment'][vi] if vi < 4 else f'variant{vi}'
                    break
            cache[addr] = (lat, lon, method)

        r['latitude'] = lat if lat is not None else ''
        r['longitude'] = lon if lon is not None else ''
        r['geocode_method'] = method or 'unresolved'

        if lat is not None:
            resolved += 1
        else:
            unresolved += 1

        if (i + 1) % 20 == 0:
            print(f'[{i+1}/{len(rows)}] resolved so far: {resolved}, unresolved: {unresolved}')

    with open(DST, 'w', newline='') as f:
        fieldnames = list(rows[0].keys())
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f'\nDone. Total: {len(rows)}, resolved: {resolved}, unresolved: {unresolved}')
    print(f'Wrote {DST}')


if __name__ == '__main__':
    main()
