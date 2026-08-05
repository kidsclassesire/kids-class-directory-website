"""One-off insert of the South Dublin candidate listings researched and reviewed in
downloads/south_dublin_new_candidates_review.md (user approved all, 2026-08-05). Writes new
rows to public.classes via the service-role key (never the public key -- see LEARNINGS.md
security note on the removed public-insert policy), then leaves latitude/longitude null for
scripts/google_geocode_missing.py to fill in on its next run.

Also fixes public.classes id=496 (Isabelle Ashe Dance), which had address = 'Multiple
Locations' -- a placeholder, not a real address -- by deleting it and inserting three
venue-specific rows instead (Ranelagh, Rathgar, Templeogue), matching the per-venue pattern
already used for Little Kickers / Turtle Tots.

Run:
  SB_SECRET=$(cat ~/Documents/kidspatch_secret.txt) python3 scripts/insert_south_dublin_candidates.py --confirm
"""

import argparse
import json
import os
import urllib.request

SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co'
TODAY = '2026-08-05'
VERIFICATION_NOTE = ('Imported from an automated nationwide web survey; not individually '
                      'phone/email verified — confirm current details before booking.')

# Each row: only fields with real values are set; everything else defaults per DEFAULTS below.
ROWS = [
    # --- Terenure & Templeogue ---
    dict(company_name='Terenure College RFC', category='Rugby',
         description='Mini rugby section at Terenure College RFC for young players.',
         class_types=['Minis Rugby'], minimum_age=6, maximum_age=12, age_range_display='U6-U12',
         address='Lakelands, Terenure College RFC, Terenure, Dublin 6W',
         website_url='https://tcrfc.ie/youth-minis/'),
    dict(company_name='Hombu Dojo Karate - Terenure', category='Martial Arts',
         description='Kids Shotokan karate classes, Thursday evenings.',
         class_types=['Kids Karate'], minimum_age=5, maximum_age=11, age_range_display='5-11 years',
         address='Terenure Sports Club, 54 Terenure Road North, Terenure, Dublin 6W',
         website_url='https://hombudojokarate.com/schedule/'),
    dict(company_name='Dancesteps Dublin', category='Dance',
         description='Ballet and modern dance classes for children and teens.',
         class_types=['Ballet', 'Modern Dance'], minimum_age=4, maximum_age=18, age_range_display='4-18 years',
         address='War Memorial Hall, Terenure, Dublin 6W',
         website_url='https://www.dancestepsdublin.com/'),
    dict(company_name="O'Hanlon Stage School", category='Drama',
         description='Dance, drama and singing stage school with Monday classes.',
         class_types=['Stage School'], minimum_age=4, maximum_age=18, age_range_display='4-18 years',
         address='Terenure College RFC, Greenlea Grove, Terenure, Dublin 6W',
         website_url='http://www.ohanlondance.ie/'),
    dict(company_name='Mezzo Music Academy - Terenure', category='Music',
         description='Kindermusik classes and instrument tuition for babies through adults.',
         class_types=['Kindermusik'], age_range_display='Babies-adult',
         address='112 Greenlea Road, Terenure, Dublin 6W',
         website_url='https://www.fun.ie/mezzo-music-academy'),
    dict(company_name='Terenure Library Chess Club', category='Other',
         description='Free drop-in chess club for kids, every second Thursday.',
         class_types=['Chess Club'], term_structure='Drop-in', price_amount=0,
         address='Terenure Library, Terenure, Dublin 6W',
         website_url='https://www.dublincity.ie/events/chess-club'),
    dict(company_name='Terenure College Swimming Pool', category='Swimming',
         description="Progressive stage-based children's swim lessons.",
         class_types=["Children's Academy Lessons"], age_range_display='Stage-based',
         address='Terenure College, Terenure, Dublin 6W',
         website_url='https://terenureswimmingpool.ie/childrensacademylessons/'),
    dict(company_name='Soccer Stars - Templeogue', category='Football',
         description='Early-years football classes, Sunday mornings.',
         class_types=['Football Classes'], minimum_age=1.5, maximum_age=8, age_range_display='18 months-8 years',
         days_of_week=['Sunday'], start_time='09:00', end_time='11:45',
         address="Our Lady's School, Terenure Road, Templeogue, Dublin 6W",
         website_url='https://soccerstars.ie/dublin/'),
    dict(company_name='Templeogue United FC - Foundations Academy', category='Football',
         description='Beginner football coaching for young children, Sunday mornings.',
         class_types=['Foundations Academy'], minimum_age=4, maximum_age=7, age_range_display='4-7 years',
         days_of_week=['Sunday'], start_time='08:45', end_time='10:00',
         address='Tymon Park all-weather pitch, Templeogue, Dublin 6W',
         website_url='https://www.templeogueunited.ie/the-academy'),
    dict(company_name="St Jude's GAA", category='GAA',
         description='Community GAA club with a football/hurling/camogie academy for young children.',
         class_types=['GAA Academy'], minimum_age=4, maximum_age=7, age_range_display='4-7 years',
         address='Wellington Lane, Templeogue, Dublin 6W',
         website_url='https://www.stjudesgaa.ie/'),
    dict(company_name='Templeogue Synge Street GAA - Bushy Academy', category='GAA',
         description='Juvenile GAA academy using Bushy Park.',
         class_types=['GAA Academy'], minimum_age=5, maximum_age=7, age_range_display='U5-U7',
         address='Bushy Park, Templeogue, Dublin 6W',
         website_url='https://www.tssgfc.com/'),
    dict(company_name='Showstoppers Stageschool Templeogue', category='Drama',
         description='Dance, singing and drama classes, Saturdays.',
         class_types=['Stage School'], minimum_age=3, maximum_age=18, age_range_display='3-18 years',
         days_of_week=['Saturday'], start_time='09:00', end_time='18:30',
         address="Our Lady's School, Terenure Road, Templeogue, Dublin 6W",
         website_url='https://www.showstoppersstageschool.com/'),
    dict(company_name='Olympian Gymnastics - Templeogue College', category='Gymnastics',
         description='Non-competitive gymnastics classes for children and teens.',
         class_types=['GymTOTS/GymKIDZ/GymTEENS'], minimum_age=3.5, maximum_age=18, age_range_display='3.5-18 years',
         address='Templeogue College, Templeville Road, Templeogue, Dublin 6W',
         website_url='https://olympiangymnastics.com/'),
    dict(company_name='Templeogue Basketball Club', category='Sports',
         description='Long-established club with a mini-basketball academy for young kids.',
         class_types=['Mini Basketball Academy'], minimum_age=5, maximum_age=11, age_range_display='5-11 years',
         address='TUD Tallaght arena (home venue), Templeogue, Dublin 6W',
         website_url='http://tbc.ie/'),
    dict(company_name='Spraoi Forest School - Bushy Park', category='Outdoor',
         description='Forest-school programme in Bushy Park; primarily runs with schools, contact for community sessions.',
         class_types=['Forest School'], age_range_display='Under 4 to 12+',
         address='St Pius Forest School, Bushy Park, Templeogue, Dublin 6W',
         website_url='https://terenurecsi.com/spraoi-forest-school'),

    # --- Rathmines & Rathgar ---
    dict(company_name='Isabelle Ashe Dance Studios - Rathgar', category='Dance',
         description='Ballet and modern theatre dance classes for young children.',
         class_types=['Ballet', 'Modern Theatre Dance'], age_range_display='From age 2',
         address='Rathgar Methodist Church, Brighton Road, Rathgar, Dublin 6',
         website_url='https://www.isabelleashedance.ie/locations'),
    dict(company_name='StageSchool Ireland - Rathgar', category='Drama',
         description='Saturday morning musical-theatre classes rotating singing, dance and drama.',
         class_types=['Musical Theatre'], minimum_age=4, maximum_age=18, age_range_display='4-18 years',
         days_of_week=['Saturday'],
         address='The High School, Danum, Zion Road, Rathgar, Dublin 6',
         website_url='https://stageschool.ie/locations/rathgar-dublin'),
    dict(company_name='Olympian Gymnastics - Rathgar', category='Gymnastics',
         description='Non-competitive gymnastics classes for kids and teens.',
         class_types=['GymKIDZ/GymTEENS'], age_range_display='Under 12, 13-17',
         address='Danum, Zion Road, Rathgar, Dublin 6, D06 YR68',
         website_url='https://olympiangymnastics.com/'),
    dict(company_name='JKS Ireland - Rathmines', category='Martial Arts',
         description='Karate/martial arts dojo.',
         class_types=['Karate'],
         address='219 Lower Rathmines Road, Rathmines, Dublin 6'),
    dict(company_name='Young European Strings School of Music', category='Music',
         description='Violin, viola, cello and double bass lessons and orchestra, from age 3.',
         class_types=['String Instrument Lessons'], minimum_age=3, age_range_display='From age 3',
         address='Christ Church, Rathgar, Dublin 6',
         website_url='https://www.youngeuropeanstrings.com/'),
    dict(company_name='Studio 6 School of Music', category='Music',
         description='Guitar, piano and drums lessons.',
         class_types=['Instrument Lessons'],
         address='10A Terenure Road East, Rathgar, Dublin 6',
         website_url='https://www.studio6school.com/'),
    dict(company_name='Rathmines Library Toddler Group', category='Parent-and-toddler',
         description='Drop-in story, song and play session for babies and preschoolers, Thursdays.',
         class_types=['Toddlers at One'], age_range_display='Babies-preschool',
         days_of_week=['Thursday'], term_structure='Drop-in',
         address='Rathmines Library, 157 Lower Rathmines Road, Rathmines, Dublin 6',
         website_url='https://www.dublincity.ie/'),
    dict(company_name='Christ Church Rathgar Parents & Toddlers', category='Parent-and-toddler',
         description='Long-running (since 2003) drop-in toddler group, Thursdays, €4/family.',
         class_types=['Parent and Toddler Group'], age_range_display='Preschool',
         days_of_week=['Thursday'], start_time='10:30', end_time='12:00', term_structure='Drop-in',
         price_amount=4, pricing_basis='Per family',
         address='Christ Church Rathgar, Rathgar, Dublin 6',
         website_url='https://christchurchrathgar.org/'),
    dict(company_name='Rathmines Junior Chess Club', category='Other',
         description='Monday/Wednesday evening chess coaching, tournaments and leagues.',
         class_types=['Chess Club'], days_of_week=['Monday', 'Wednesday'],
         address='Kenilworth Bowling Club, Grosvenor Square, Rathmines, Dublin 6',
         website_url='https://rathminesjuniorchessclub.wordpress.com/'),
    dict(company_name='Rathmines Forest School', category='Outdoor',
         description='Weekly after-school forest sessions plus holiday camps in a walled woodland garden.',
         class_types=['Forest School'], minimum_age=5, maximum_age=12, age_range_display='5-12 years',
         address='96 Rathmines Road Upper, Rathmines, Dublin 6',
         website_url='https://bookwhen.com/rathminesforestschool'),
    dict(company_name='Ashbrook Tennis Club', category='Tennis',
         description='Junior tennis coaching plus Easter/summer camps.',
         class_types=['Junior Coaching'],
         address='Bushes Lane, off Grosvenor Road, Rathgar, Dublin 6',
         website_url='https://www.ashbrooktennisclub.ie/'),
    dict(company_name='LCC Tennis - Leinster Cricket Club', category='Tennis',
         description='Level-graded junior tennis groups plus youth cricket teams.',
         class_types=['Junior Tennis'], days_of_week=['Saturday', 'Tuesday', 'Wednesday'],
         address='1 Observatory Lane, Rathmines, Dublin 6',
         website_url='https://www.lccsports.net/'),
    dict(company_name='Dartry Health Club - Kids Swimming Lessons', category='Swimming',
         description="Swim Ireland-accredited children's swim lessons on the Milltown/Ranelagh/Rathgar border.",
         class_types=['Kids Swim Lessons'], age_range_display='Levelled programme',
         address='31 Palmerston Gardens, Dartry, Rathgar, Dublin 6, D06 FX39',
         website_url='https://www.iconichealthclubs.ie/dartry'),
    dict(company_name='STARCAMP Rathmines', category='Camps',
         description='Performing-arts-themed Easter/summer day camp.',
         class_types=['STARCAMP', 'STARCREW'], minimum_age=4, maximum_age=12, age_range_display='4-12 years',
         address='Rathmines-St Louis High School, Rathmines, Dublin 6',
         website_url='https://starcamp.ie/'),
    dict(company_name='Alive Outside Summer Camp - Rathgar', category='Camps',
         description='Outdoor adventure, sport and STEM summer camp with a Killruddery day trip.',
         class_types=['Summer Camp'], minimum_age=7, maximum_age=13, age_range_display='7-13 years',
         address='The High School, Zion Road, Rathgar, Dublin 6',
         website_url='https://aliveoutside.ie/'),

    # --- Milltown & Ranelagh ---
    dict(company_name='Olympian Gymnastics - Milltown', category='Gymnastics',
         description='Non-competitive gymnastics classes for kids and teens.',
         class_types=['GymKIDZ/GymTEENS'], age_range_display='Under 12, 13-17',
         address='Milltown Road, Milltown, Dublin 6',
         website_url='https://olympiangymnastics.com/'),
    dict(company_name='Isabelle Ashe Dance Studios - Ranelagh', category='Dance',
         description='Ballet and modern theatre dance classes for young children.',
         class_types=['Ballet', 'Modern Theatre Dance'], age_range_display='From age 2',
         address='Wesley House, Leeson Park, Ranelagh, Dublin 6',
         website_url='https://www.isabelleashedance.ie/locations'),
    dict(company_name='The Independent Theatre Workshop', category='Drama',
         description='Performing arts school teaching singing, dance and drama; runs classes in Ranelagh.',
         class_types=['Performing Arts'], minimum_age=3, age_range_display='3-adult',
         address='Ranelagh, Dublin 6',
         website_url='https://itwstudios.ie/'),
    dict(company_name='Ranelagh Gaels GAA - Juvenile Academy', category='GAA',
         description='Community GAA club founded in Ranelagh; football/hurling academy for young children.',
         class_types=['GAA Academy'], minimum_age=5, maximum_age=7, age_range_display='5-7 years',
         address='KPS, 96 Rathmines Road Upper, Ranelagh, Dublin 6',
         website_url='https://www.ranelaghgaels.ie/'),
    dict(company_name='Hombu Dojo Karate - Ranelagh', category='Martial Arts',
         description='Shotokan karate dojo with dedicated kids classes.',
         class_types=['Kids Karate'], minimum_age=5, maximum_age=11, age_range_display='5-11 years',
         address='Rear of Cullenswood Park, Ranelagh, Dublin 6, D06 Y313',
         website_url='https://hombudojokarate.com/'),
    dict(company_name='Mount Pleasant Tennis Club', category='Tennis',
         description='700+ member club with 11 courts and junior coaching.',
         class_types=['Junior Coaching'],
         address='Mountpleasant Square, Ranelagh, Dublin 6',
         website_url='https://www.mountpleasantltc.ie/'),
    dict(company_name='Alto School of Music - Ranelagh', category='Music',
         description='Group/private piano, guitar, violin and other instrument lessons delivered in local schools.',
         class_types=['Instrument Lessons'], age_range_display='~5-12 years',
         address='Local primary schools, Ranelagh, Dublin 6',
         website_url='https://www.altoschoolofmusic.com/'),
    dict(company_name='Soccer Stars - Ranelagh', category='Football',
         description='Early-years football coaching, Saturdays.',
         class_types=['Football Classes'], minimum_age=1.5, maximum_age=8, age_range_display='18 months-8 years',
         days_of_week=['Saturday'], start_time='10:00', end_time='11:45',
         address='Beechwood Community Centre, Mountain View Road, Ranelagh, Dublin 6',
         website_url='https://soccerstars.ie/'),

    # --- Rathfarnham & Crumlin ---
    dict(company_name='Swan Leisure - Crumlin', category='Swimming',
         description='Children\'s and family swim lessons (SwimFit programme).',
         class_types=['SwimFit'], age_range_display='Baby-14 years',
         address='80A Windmill Road, Crumlin, Dublin 12, D12 WK5A',
         website_url='https://www.swanleisure.ie/swimming'),
    dict(company_name='Crumlin United FC', category='Football',
         description='Football academy from young children through to U18.',
         class_types=['Football Academy'], minimum_age=5, maximum_age=18, age_range_display='5-U18',
         address='Pearse Park, 177 Windmill Road, Crumlin, Dublin 12',
         website_url='https://crumlinunited.academy/under-12s/'),
    dict(company_name='Crumlin Boxing Club', category='Martial Arts',
         description='Junior boxing club.',
         class_types=['Junior Boxing'],
         address="Willie Pearse Park, Windmill Road, Crumlin, Dublin 12, D12 FH60"),
    dict(company_name='Crumlin Freestyle Kickboxing Club', category='Martial Arts',
         description='Junior kickboxing class.',
         class_types=['Junior Kickboxing'], minimum_age=8, maximum_age=16, age_range_display='8-16 years',
         address='Crumlin Integrated College, 10 Glenavy Road, Crumlin, Dublin 12',
         website_url='http://crumlinfkc.blogspot.com/p/about.html'),
    dict(company_name='Cor Dance Academy', category='Dance',
         description='Dance academy in Crumlin.',
         class_types=['Dance Classes'],
         address='Crumlin, Dublin 12'),
    dict(company_name='Gym Plus Rathfarnham - Swim Plus Academy', category='Swimming',
         description='Multi-level learn-to-swim programme.',
         class_types=['Learn to Swim'], age_range_display='Multi-level',
         address='Nutgrove Retail Park, Nutgrove Avenue, Rathfarnham, Dublin 14, D14 Y3C5',
         website_url='https://gymplus.ie/swimming-rathfarnham/'),
    dict(company_name="Knights of Éanna Chess Club", category='Other',
         description='Junior chess coaching.',
         class_types=['Chess Club'], age_range_display='School-age',
         address='Coláiste Éanna, Rathfarnham, Dublin 16',
         website_url='https://www.knightsofeanna.ie/'),
    dict(company_name="Helen's Art Space", category='Arts and crafts',
         description='Saturday and Thursday art classes for primary school children.',
         class_types=['Art Classes'], minimum_age=7, maximum_age=12, age_range_display='7-12 years',
         address='Studio 23, Marlay Craft Courtyard, Rathfarnham, Dublin 16',
         website_url='https://www.helensartspace.com/'),
    dict(company_name='Leicester Celtic FC', category='Football',
         description='Football academy from young children through adult.',
         class_types=['Football Academy'], minimum_age=4, age_range_display='4-adult',
         address='Loreto Park, Nutgrove, Rathfarnham, Dublin 14',
         website_url='https://www.leicesterceltic.ie/location.html'),
    dict(company_name='Ballyroan Karate Club', category='Martial Arts',
         description='Karate club.',
         class_types=['Karate'],
         address='Marian Road, Rathfarnham, Dublin 16'),
    dict(company_name='Summit Judo/Jiu-Jitsu Academy', category='Martial Arts',
         description='Judo and Brazilian Jiu-Jitsu classes for kids, teens and adults.',
         class_types=['Judo', 'Jiu-Jitsu'], age_range_display='4-7, 8-12, teens',
         address="St. Columba's College Gym, 16 Kilmashogue Lane, Whitechurch, Rathfarnham, Dublin 16",
         website_url='https://irish-pages.ie/listing/ireland/rathfarnham/sports-club/summit-judo-bjj'),
    dict(company_name='Olympian Gymnastics - Nutgrove', category='Gymnastics',
         description='Non-competitive gymnastics classes for children and teens (GymTOTS/GymKIDZ/GymTEENS).',
         class_types=['GymTOTS/GymKIDZ/GymTEENS'], minimum_age=1.5, maximum_age=16, age_range_display='18 months-16 years',
         address='Unit 1/2B Nutgrove Shopping Centre, Nutgrove Way, Rathfarnham, Dublin 14',
         phone_number='+353 86 082 5737',
         website_url='https://olympiangymnastics.com/'),
    dict(company_name='Artzone - Rathfarnham', category='Arts and crafts',
         description="Children's art classes, camps and parties.",
         class_types=['Art Classes'], minimum_age=5, maximum_age=12, age_range_display='5-12 years',
         address='VFI Court, Castleside Drive, Rathfarnham, Dublin 14, D14 EY73',
         email_address='bookings@artzone.ie',
         website_url='https://artzone.ie/'),
]

# Isabelle Ashe Dance's Templeogue location has an unconfirmed address -- add with just the
# neighborhood rather than guessing a street.
ROWS.append(dict(
    company_name='Isabelle Ashe Dance Studios - Templeogue', category='Dance',
    description='Ballet and modern theatre dance classes for young children.',
    class_types=['Ballet', 'Modern Theatre Dance'], age_range_display='From age 2',
    address='Templeogue, Dublin 6W',
    website_url='https://www.isabelleashedance.ie/locations',
))

DEFAULTS = dict(
    parental_requirement='Not Stated', price_currency='EUR',
    source_urls=None,  # filled per-row below from website_url when not explicitly set
    date_verified=TODAY, verification_status=VERIFICATION_NOTE,
)


def sb_headers(secret):
    return {'apikey': secret, 'Authorization': f'Bearer {secret}'}


def build_payload(row):
    payload = {**DEFAULTS, **row}
    if not payload.get('source_urls') and payload.get('website_url'):
        payload['source_urls'] = [payload['website_url']]
    payload.pop('source_urls', None) if not payload.get('source_urls') else None
    return payload


def insert_row(secret, payload):
    headers = {**sb_headers(secret), 'Content-Type': 'application/json', 'Prefer': 'return=representation'}
    req = urllib.request.Request(
        f'{SUPABASE_URL}/rest/v1/classes', data=json.dumps([payload]).encode(),
        headers=headers, method='POST',
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())[0]


def delete_row(secret, row_id):
    headers = sb_headers(secret)
    req = urllib.request.Request(
        f'{SUPABASE_URL}/rest/v1/classes?id=eq.{row_id}', headers=headers, method='DELETE',
    )
    with urllib.request.urlopen(req, timeout=20):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args()

    secret = os.environ['SB_SECRET']
    print(f'{len(ROWS)} rows to insert.')
    print('Also: delete id=496 (Isabelle Ashe Dance, address="Multiple Locations" placeholder) '
          '-- replaced by the 3 venue-specific rows above.')

    if not args.confirm:
        print('\nDry run (pass --confirm to write). Sample:')
        for row in ROWS[:5]:
            print(f'  {row["company_name"]} [{row["category"]}] -- {row["address"]}')
        return

    print('\nDeleting placeholder row id=496...')
    delete_row(secret, 496)

    inserted = []
    for i, row in enumerate(ROWS):
        payload = build_payload(row)
        try:
            result = insert_row(secret, payload)
            inserted.append(result)
            print(f'[{i+1}/{len(ROWS)}] Inserted id={result["id"]}: {row["company_name"]}')
        except Exception as e:
            print(f'[{i+1}/{len(ROWS)}] FAILED: {row["company_name"]}: {e}')

    with open('/Users/davidmacmahon/kids-class-directory-website/downloads/south_dublin_candidates_inserted.json', 'w') as f:
        json.dump(inserted, f, indent=2)
    print(f'\nInserted {len(inserted)}/{len(ROWS)} rows.')
    print('Next: run scripts/google_geocode_missing.py to fill in coordinates, then '
          'scripts/generate_business_pages.py && scripts/generate_landing_pages.py to publish.')


if __name__ == '__main__':
    main()
