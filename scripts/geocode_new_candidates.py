import json
import time
import urllib.request
import urllib.parse

SRC = '/Users/davidmacmahon/kids-class-directory-website/downloads/cleaned_new_candidates.json'
CACHE_PATH = '/private/tmp/claude-501/-Users-davidmacmahon-kids-class-directory-website/c257683e-3ad5-4460-b1f5-15a4e037bc6e/scratchpad/geocode_cache_batch2.json'

# Wider Dublin + commuter-belt bounding box (this batch may include Fingal/Lucan/etc, not just South Dublin)
BOX = (53.15, 53.65, -6.55, -5.95)

with open(SRC) as f:
    data = json.load(f)

addresses = sorted(set(
    d['address'] for d in data
    if d.get('address') and not (d.get('latitude') and d.get('longitude'))
))
print(f'{len(addresses)} unique addresses to geocode')


def geocode_query(q, retries=3):
    url = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode({
        'format': 'json', 'limit': 1, 'countrycodes': 'ie', 'q': q
    })
    req = urllib.request.Request(url, headers={
        'User-Agent': 'kids-class-directory-geocoder/1.0 (contact: davidmacmahon1@gmail.com)'
    })
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                results = json.loads(resp.read().decode())
            if results:
                return float(results[0]['lat']), float(results[0]['lon'])
            return None, None
        except Exception as e:
            if attempt == retries - 1:
                print(f'    (giving up on this query after {retries} attempts: {e})')
                return None, None
            time.sleep(2)
    return None, None


def in_box(lat, lon):
    return BOX[0] <= lat <= BOX[1] and BOX[2] <= lon <= BOX[3]


try:
    with open(CACHE_PATH) as f:
        cache = json.load(f)
except FileNotFoundError:
    cache = {}

found_count = sum(1 for v in cache.values() if v.get('latitude') is not None)
remaining = [a for a in addresses if a not in cache]
print(f'{len(cache)} already done ({found_count} found), {len(remaining)} remaining')

for i, addr in enumerate(remaining):
    parts = [p.strip() for p in addr.split(',') if p.strip()]

    attempts = [addr]
    if len(parts) > 1:
        attempts.append(', '.join(parts[1:]))  # drop leading venue/building name
    if len(parts) > 2:
        attempts.append(', '.join(parts[-2:]))  # area/city-level only

    result = None
    used = None
    for q in attempts:
        lat, lon = geocode_query(q)
        time.sleep(1.1)
        if lat and in_box(lat, lon):
            result = (lat, lon)
            used = q
            break

    if result:
        cache[addr] = {'latitude': result[0], 'longitude': result[1]}
        found_count += 1
        print(f'[{i+1}/{len(remaining)}] OK via "{used}": {addr}')
    else:
        cache[addr] = {'latitude': None, 'longitude': None}
        print(f'[{i+1}/{len(remaining)}] NOT FOUND: {addr}')

    with open(CACHE_PATH, 'w') as f:
        json.dump(cache, f, indent=2)

print(f'\nGeocoded {found_count}/{len(addresses)} addresses successfully so far')
