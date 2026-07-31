import json
import re
from collections import Counter

SRC = '/Users/davidmacmahon/kids-class-directory-website/downloads/all_normalized_candidates.json'
EXISTING = '/Users/davidmacmahon/kids-class-directory-website/south_dublin_kids_activities.json'

data = json.load(open(SRC))
existing = json.load(open(EXISTING))

# canonical category -> keywords that map to it (checked in order, first match wins)
CANONICAL = [
    ('Football', ['football']),
    ('GAA', ['gaa']),
    ('Rugby', ['rugby']),
    ('Hockey', ['hockey']),
    ('Tennis', ['tennis']),
    ('Horse Riding', ['horse riding', 'horse rid']),
    ('Basketball', ['basketball']),
    ('Martial Arts', ['martial arts', 'karate', 'taekwondo', 'boxing', 'kickboxing']),
    ('Swimming', ['swim']),
    ('Watersports', ['sailing', 'surfing', 'water sports', 'watersports']),
    ('Gymnastics', ['gymnastic']),
    ('Athletics', ['athletic']),
    ('Team Sports', ['team sports', 'badminton', 'pickleball', 'volleyball', 'sports camp']),
    ('Dance', ['dance', 'ballet', 'irish dance', 'jazz', 'tap ', 'hip hop', 'kids dance']),
    ('Music', ['music', 'piano', 'guitar', 'violin', 'viola', 'cello', 'drums', 'ukulele',
               'choir', 'singing', 'orchestra', 'keyboard', 'flute', 'wind & brass', 'bass',
               'fiddle', 'song writing']),
    ('Drama', ['drama', 'acting', 'musical theatre', 'speech & drama']),
    ('Arts and crafts', ['art & craft', 'art, craft', 'arts and crafts', 'art &crafts', 'art & crafts',
                          'drawing', 'painting', 'pottery', 'sculpture', 'printmaking', 'sewing',
                          'knitting', 'woodworking', 'card making', 'paper crafts', 'kids art club',
                          'kids craft']),
    ('STEM', ['stem', 'coding', 'robotics', 'science & stem']),
    ('Languages', ['language', 'irish language', 'spanish', ' irish,']),
    ('Academic Support', ['grinds', 'homework club', 'academic support', 'exam prep', 'study skills',
                           'maths', 'phonics', 'reading/writing']),
    ('Camps', ['camp']),
    ('Developmental', ['baby massage', 'baby & early learning', 'sensory', 'messy play',
                        'movement & play', 'tummy time', 'baby sign language', 'sign language',
                        'music & movement for tots', 'baby yoga', 'kids & family yoga',
                        'baby swimming']),
    ('Parent-and-toddler', ['playgroup', 'toddler group', 'parent & toddler', 'parent-and-toddler',
                             'storytime', 'dads & babies']),
    ('Outdoor', ['forest school', 'nature & outdoor camp']),
    ('Adventure/Scouts', ['scouts', 'adventure/scouts']),
    ('STEM', ['technical', 'coderdojo']),
    ('Cooking', ['cooking', 'baking', 'cake decoration']),
    ('Developmental', ['developmental', 'baby + toddler', 'baby and toddler classes']),
    ('Sports', ['sports', 'sport']),  # generic fallback, checked after specific sports above
]

# Terms that are adult-oriented wellness/fitness and should NOT count as a kids class
# unless a kids/family qualifier is present in the same compound string.
ADULT_WELLNESS_TERMS = ['yoga', 'pilates', 'meditation', 'wellbeing', 'wellness', 'mindfulness',
                         'tai chi', 'qigong', 'reiki', 'sound bath', 'breathwork', 'fitness',
                         'personal training', 'gym & strength', 'crossfit', 'zumba', 'homeopathy',
                         'counselling']
KIDS_QUALIFIERS = ['kids', 'family', 'baby', 'toddler', 'tots', 'junior', 'teen', 'youth',
                    'children', "children's"]

# Strong exclude signals: retail, food, adult-only services, non-class listings
EXCLUDE_TERMS = ['eat', 'apparel', 'cake', 'caterer', 'jewellery', 'photograph', 'sleep consultant',
                 'skincare', 'gift', 'homeware', 'hotel', 'brand', 'kids store', 'kids shoes',
                 'nursey interiors', 'nursery interiors', 'baby essentials', 'weaning',
                 'montessori school', 'crèche', 'creche', 'childminder', 'party entertainer',
                 'party venue', 'parks + playground', 'beaches', 'books', 'driving lesson',
                 'business & entrepreneurship', 'image consultancy', 'image, styling',
                 'older adults', 'adult beginners', 'antenatal', 'breast feeding', 'breastfeeding',
                 'for parents', 'social & meetup', 'social,', ', social', 'cinema/film',
                 'first aid', 'weight management', 'teacher training', 'transition year',
                 'a-level', 'junior cycle', 'leaving cert', 'indoor', 'outdoor', 'other',
                 'mid range family hotels', 'high end family friendly hotels',
                 'budget family friendly hotels', 'exercise', 'cooking', 'wellbeing']


def segments(cat):
    return [s.strip().lower() for s in re.split(r'[;,]', cat) if s.strip()]


# Hard vetoes: adult-only signals that should never count as a kids' class
# regardless of what else is in the compound category string.
ADULT_VETO_TERMS = ['weight management', 'weight loss', 'older adults', 'adult beginners',
                     'menopause', 'personal training']

# Counties/cities clearly outside the Dublin area this directory covers.
OUT_OF_AREA_TERMS = ['galway', 'cork', 'limerick', 'kerry', 'killarney', 'sligo', 'mayo',
                      'westport', 'wexford', 'waterford', 'kilkenny', 'clare', 'ennis',
                      'donegal', 'leitrim', 'roscommon', 'longford', 'cavan', 'monaghan',
                      'tipperary', 'laois', 'offaly', 'carlow', 'northern ireland', 'belfast']


def classify(category):
    if not category:
        return None
    whole = category.lower()
    if any(term in whole for term in ADULT_VETO_TERMS):
        return None
    segs = segments(category)

    has_kids_qualifier = any(any(q in s for q in KIDS_QUALIFIERS) for s in segs)

    # Check segments IN THE SOURCE'S OWN ORDER first (source data lists tags
    # most-specific/primary-first, e.g. "Acting & Drama, Music, Drama & Performance"
    # is really a Drama listing, not Music) -- for each segment, in order, see if
    # any canonical bucket matches it. This must come before the whole-string scan
    # below, which would otherwise let an unrelated later tag (e.g. a stray "Music"
    # segment on a Drama listing) win just because that canonical bucket happens to
    # be earlier in CANONICAL's list order.
    for seg in segs:
        for canon, keywords in CANONICAL:
            for kw in keywords:
                if kw in seg:
                    return canon

    # Fallback: whole-string scan in CANONICAL priority order, for cases where
    # a keyword spans across how the string got split (rare, but keeps old behavior
    # as a safety net rather than silently excluding a matchable row).
    for canon, keywords in CANONICAL:
        for kw in keywords:
            if kw in whole:
                return canon

    # adult wellness only counts if a kids qualifier is present alongside it
    for term in ADULT_WELLNESS_TERMS:
        if term in whole and has_kids_qualifier:
            return 'Developmental'

    return None  # no positive match -> excluded by default


def is_out_of_area(address):
    if not address:
        return False
    a = address.lower()
    return any(term in a for term in OUT_OF_AREA_TERMS)


results = []
excluded_reasons = Counter()
out_of_area_count = 0
for d in data:
    canon = classify(d.get('category'))
    if canon is None:
        excluded_reasons[d.get('category')] += 1
        continue
    if is_out_of_area(d.get('address')):
        out_of_area_count += 1
        continue
    d2 = dict(d)
    d2['category'] = canon
    d2['raw_category'] = d.get('category')
    results.append(d2)

print(f'Total candidates: {len(data)}')
print(f'Excluded (no class signal): {len(data) - len(results) - out_of_area_count}')
print(f'Excluded (clearly outside Dublin area): {out_of_area_count}')
print(f'Kept (in-scope class, Dublin-area): {len(results)}')

kept_cats = Counter(r['category'] for r in results)
print('\nKept, by canonical category:')
for c, n in kept_cats.most_common():
    print(f'  {n:4d}  {c}')

print(f'\nTop 15 excluded raw categories (by row count):')
for c, n in excluded_reasons.most_common(15):
    print(f'  {n:4d}  {c}')

def norm_name(v):
    if not v:
        return ''
    return re.sub(r'[^a-z0-9]+', ' ', v.lower()).strip()


def norm_addr(v):
    if not v:
        return ''
    s = v.lower().replace('co. ', 'co ').replace('co.', 'co ')
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


existing_keys = set()
existing_websites = set()
existing_phones = set()
for e in existing:
    existing_keys.add((norm_name(e.get('company_name')), norm_addr(e.get('address'))))
    if e.get('website_url'):
        existing_websites.add(e['website_url'].strip().lower().rstrip('/'))
    if e.get('phone_number'):
        existing_phones.add(re.sub(r'\D', '', e['phone_number']))

new_rows = []
already_present = 0
for r in results:
    key = (norm_name(r.get('company_name')), norm_addr(r.get('address')))
    site = (r.get('website_url') or '').strip().lower().rstrip('/')
    phone = re.sub(r'\D', '', r.get('phone_number') or '')
    if key in existing_keys or (site and site in existing_websites) or (phone and phone in existing_phones):
        already_present += 1
        continue
    new_rows.append(r)

print(f'\nOf the {len(results)} kept rows: {already_present} already exist in the live 67, {len(new_rows)} are genuinely new')

# Dedup the genuinely-new rows against each other (same fuzzy logic: name+address, or matching website/phone)
seen_keys = set()
seen_sites = set()
seen_phones = set()
deduped_new = []
internal_dupes = 0
for r in new_rows:
    key = (norm_name(r.get('company_name')), norm_addr(r.get('address')))
    site = (r.get('website_url') or '').strip().lower().rstrip('/')
    phone = re.sub(r'\D', '', r.get('phone_number') or '')
    if key in seen_keys or (site and site in seen_sites) or (phone and phone in seen_phones):
        internal_dupes += 1
        continue
    seen_keys.add(key)
    if site:
        seen_sites.add(site)
    if phone:
        seen_phones.add(phone)
    deduped_new.append(r)

print(f'Internal duplicates among the new rows (same business scraped from multiple sources): {internal_dupes}')
print(f'Final: {len(deduped_new)} new, in-scope, deduped candidate rows')

out_path = '/private/tmp/claude-501/-Users-davidmacmahon-kids-class-directory-website/c257683e-3ad5-4460-b1f5-15a4e037bc6e/scratchpad/cleaned_new_candidates.json'
with open(out_path, 'w') as f:
    json.dump(deduped_new, f, indent=2, ensure_ascii=False)
print(f'\nWrote {len(deduped_new)} rows to {out_path}')

missing_addr = sum(1 for r in deduped_new if not r.get('address'))
missing_geo = sum(1 for r in deduped_new if not r.get('latitude') or not r.get('longitude'))
print(f'Of those: {missing_addr} missing address entirely, {missing_geo} missing lat/lon (all of them, since source data never had coordinates)')
