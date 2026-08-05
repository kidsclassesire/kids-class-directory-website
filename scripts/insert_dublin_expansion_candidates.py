"""One-off insert of the Dublin-expansion candidate listings researched and reviewed in five
downloads/*_new_candidates_review.md files (user approved a specific curated subset of each,
2026-08-05). This is the second batch after South Dublin (see
scripts/insert_south_dublin_candidates.py) and covers infill towns across:

  - downloads/north_county_dublin_new_candidates_review.md   (Howth, Sutton, Baldoyle,
    Portmarnock, Donabate, Rush)
  - downloads/southside_coastal_new_candidates_review.md     (Killiney, Glenageary, Cabinteely,
    Stepaside, Deansgrange, Loughlinstown)
  - downloads/west_dublin_new_candidates_review.md           (Palmerstown, Inchicore, Clonsilla,
    Ongar, Hartstown, Corduff)
  - downloads/northside_inner_new_candidates_review.md       (Glasnevin, Phibsborough, Marino,
    Fairview, Cabra)
  - downloads/northside_outer_new_candidates_review.md       (Raheny, Donaghmede, Kilbarrack,
    Artane, Coolock, Santry, Finglas, Ballymun)

Writes new rows to public.classes via the service-role key (never the public key -- see
LEARNINGS.md security note on the removed public-insert policy), then leaves latitude/longitude
null for scripts/google_geocode_missing.py to fill in on its next run.

Run:
  SB_SECRET=$(cat ~/Documents/kidspatch_secret.txt) python3 scripts/insert_dublin_expansion_candidates.py --confirm
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
    # --- Howth ---
    dict(company_name='Howth Yacht Club', category='Watersports',
         description='Junior sailing courses and members\' courses for kids and teens.',
         class_types=['Junior Sailing'], age_range_display='Kids and teens',
         address='Middle Pier, Howth Harbour, Howth, Co. Dublin, D13 E6V3',
         website_url='https://hyc.ie/junior'),
    dict(company_name='Howth Music School', category='Music',
         description='Music lessons for children and adults, with reduced rates for beginner juniors.',
         class_types=['Music Lessons'], age_range_display='Children and adults',
         address='14 Abbey Street, Howth, Co. Dublin, D13 EY77',
         website_url='https://howthmusicschool.com/'),
    dict(company_name='Metropolitan School of Dance - Howth/Sutton', category='Dance',
         description='Dance classes on the Howth/Sutton border; a separate venue from the '
                      'existing Balbriggan/Leixlip location.',
         class_types=['Dance Classes'], minimum_age=3, age_range_display='Age 3-young adult',
         address='Burrow National School, Howth Road, Sutton, Dublin 13',
         website_url='https://www.metropolitanschoolofdance.ie/'),
    dict(company_name='Howth Library - Toddler Time', category='Parent-and-toddler',
         description='Drop-in toddler story and play session, Thursdays.',
         class_types=['Toddler Time'], age_range_display='Toddlers',
         days_of_week=['Thursday'], start_time='10:00', term_structure='Drop-in',
         address='Howth Library, Howth, Co. Dublin',
         phone_number='+353 1 890 5026'),

    # --- Sutton ---
    dict(company_name='Sutton Dinghy Club', category='Watersports',
         description='Junior sailing courses including Optimist/Laser and a "Taste of Sailing" '
                      'programme for young beginners.',
         class_types=['Junior Sailing'], age_range_display='Children',
         address='Strand Road, Sutton, Dublin 13',
         website_url='https://www.sdc.ie/junior-sailing'),
    dict(company_name='Sutton Lawn Tennis Club', category='Tennis',
         description='Junior tennis coaching, including summer coaching weeks.',
         class_types=['Junior Coaching'], minimum_age=5, maximum_age=12, age_range_display='5-12 years',
         address='176 Howth Road, Sutton, Dublin 13',
         website_url='https://thekerrymam.ie/directory/all/sutton-lawn-tennis-club'),

    # --- Baldoyle ---
    dict(company_name='Baldoyle United FC', category='Football',
         description='Junior football academy, Saturday mornings.',
         class_types=['Junior Academy'], minimum_age=4, maximum_age=8, age_range_display='4-8 years',
         days_of_week=['Saturday'],
         address='Brookstone Road, Baldoyle, Dublin 13',
         website_url='https://www.baldoyleunited.ie/'),
    dict(company_name='Song and Dance Stage School', category='Drama',
         description='Dance, singing and drama stage school classes.',
         class_types=['Stage School'], minimum_age=3, age_range_display='3+ years',
         address='27 College Street, Baldoyle, Dublin 13, D13 K034',
         website_url='https://www.songanddanceireland.com/'),
    dict(company_name='The Music Academy - Baldoyle', category='Music',
         description='Music tuition based at St Laurence\'s NS junior building.',
         class_types=['Music Lessons'], age_range_display='School-age',
         address="St Laurence's NS (Junior Building), Grange Road, Baldoyle, D13 XE37",
         website_url='https://www.facebook.com/themusicacademybaldoyle'),
    dict(company_name='Odett School of Ballet / DSA - Baldoyle', category='Dance',
         description='Ballet and Dance Sing Act programmes at Baldoyle Racecourse Community Centre.',
         class_types=['Ballet', 'Dance Sing Act'],
         address='Racecourse Community Centre, Baldoyle, D13 X226',
         website_url='https://www.baldoyleracecoursecc.ie/childrens-activities'),

    # --- Portmarnock ---
    dict(company_name='Naomh Mearnóg GAA', category='GAA',
         description='GAA nursery for young children, Saturday mornings, late August to June.',
         class_types=['GAA Nursery'], minimum_age=4, maximum_age=7, age_range_display='4-7 years',
         days_of_week=['Saturday'],
         address='Naomh Mearnóg GAA Club, Blackwood Lane, Portmarnock, Co. Dublin',
         website_url='https://www.naomhmearnog.ie/juvenile/nursery'),
    dict(company_name='Portmarnock Athletic Club', category='Athletics',
         description='Juvenile athletics section based at Portmarnock Sports & Leisure Club.',
         class_types=['Juvenile Athletics'],
         address='Portmarnock Sports & Leisure Club, Blackwood Lane, Portmarnock, Co. Dublin',
         website_url='https://www.portmarnockathleticclub.ie/juvenile'),

    # --- Donabate ---
    dict(company_name="St Patrick's GAA Donabate", category='GAA',
         description='Juvenile GAA academy (Páistí Pats).',
         class_types=['GAA Academy'],
         address='Robbie Farrell Park, Ballymastone, Donabate, Co. Dublin',
         website_url='https://www.stpatsgaa.com/'),
    dict(company_name='Donabate Portrane Tennis Club', category='Tennis',
         description='Junior tennis coaching through red/orange/green/yellow ball progression; members only.',
         class_types=['Junior Coaching'], minimum_age=5, age_range_display='5+ through teens',
         address='c/o Donabate Golf Club, New Road, Donabate, Co. Dublin, K36 PK70',
         website_url='https://www.donabatetennis.com/coaching'),
    dict(company_name='Donabate Golf Club', category='Sports',
         description='Junior golf programme.',
         class_types=['Junior Golf'], minimum_age=8, maximum_age=20, age_range_display='8-20 years',
         address='New Road, Donabate, Co. Dublin',
         website_url='https://www.donabategolfclub.com/members/juniors'),

    # --- Rush ---
    dict(company_name='Rush Sailing Club (RSC)', category='Watersports',
         description='Junior sailing programme, April-September, plus summer camps.',
         class_types=['Junior Sailing'], minimum_age=8, maximum_age=17, age_range_display='8-17 years',
         address='Linkside, Rogerstown, Rush, Co. Dublin, K56 RH52',
         website_url='https://www.rushsc.ie/'),
    dict(company_name='Rush Athletic FC (RAFC)', category='Football',
         description='Schoolboy football teams from U7 through U18.',
         class_types=['Schoolboy Football'], age_range_display='U7-U18',
         address='Skerries Road, Rush, Co. Dublin',
         website_url='https://rushafc.webnode.page/'),
    dict(company_name="St Maur's GAA (Naomh Maur)", category='GAA',
         description='Community GAA club with juvenile teams, founded 1928.',
         class_types=['GAA Juvenile Teams'],
         address='Park Road, Rush, Co. Dublin',
         website_url='https://www.clubinfo.ie/club/st-maurs-gfc'),
    dict(company_name='Rush Multipurpose Youth Facility', category='Music',
         description='Music club for young children covering singing and instruments.',
         class_types=['Rush Rocks Music Club'], age_range_display='Young children',
         address='Millbank, Rush, Co. Dublin, K56 CC90',
         website_url='https://www.rmyf.ie/'),

    # --- Killiney ---
    dict(company_name='Cluny Park Tennis Club', category='Tennis',
         description='Junior tennis coaching groups, Sunday mornings.',
         class_types=['Junior Coaching'], days_of_week=['Sunday'],
         address='Cluny Grove (Rochestown Domain), Killiney, Co. Dublin',
         website_url='https://www.clunytennis.ie/'),
    dict(company_name='Ballybrack FC', category='Football',
         description='Football academy (Tigers) for young children, serving the Ballybrack/'
                      'Loughlinstown/Cabinteely/Shankill/Killiney catchment.',
         class_types=['Tigers Academy'], minimum_age=5, maximum_age=7,
         age_range_display='5-7 years (Tigers); club runs 7-18',
         address='Coolevin, Ballybrack, Co. Dublin',
         website_url='https://www.ballybrackfc.com/'),
    dict(company_name='KidsCraic - Killiney Hill Adventure Camp', category='Camps',
         description='Outdoor adventure camp at Killiney Hill Park.',
         class_types=['Adventure Camp'], minimum_age=5, maximum_age=12, age_range_display='5-12 years',
         address='Killiney Hill Park, Killiney, Co. Dublin',
         website_url='https://www.kidscraic.com/activities'),

    # --- Glenageary ---
    dict(company_name='Glenageary Lawn Tennis Club', category='Tennis',
         description='Junior tennis section with a junior coaching programme.',
         class_types=['Junior Coaching'],
         address='Silchester Road, Glenageary, Co. Dublin, A96 YY20',
         website_url='https://www.glenagearyltc.ie/'),
    dict(company_name='StageSchool Ireland - Glenageary', category='Drama',
         description='Musical theatre classes rotating singing, dance and drama.',
         class_types=['Musical Theatre'], minimum_age=4, maximum_age=18, age_range_display='4-18 years',
         address='Rathdown School, Upper Glenageary Road, Glenageary, Co. Dublin',
         website_url='https://stageschool.ie/'),

    # --- Cabinteely ---
    dict(company_name='Cabinteely FC', category='Football',
         description='Early-years football academy (Cubs & Kittens) at Kilbogget Park.',
         class_types=['Cubs & Kittens Academy'], minimum_age=4, age_range_display='From age 4 (born 2019-2022)',
         address='Large Astro Pitch, Kilbogget Park, Churchview Road, Cabinteely, Co. Dublin, A96 PC84',
         website_url='https://www.cabinteelyfc.ie/football-for-kids-in-south-dublin'),
    dict(company_name='FoxCab GAA (Foxrock-Cabinteely)', category='GAA',
         description='Juvenile GAA academy (FoxCub), running at Kilbogget Park (spring/summer) '
                      'and Beckett Park Astro, Cherrywood (autumn/winter).',
         class_types=['GAA Academy'], minimum_age=4, maximum_age=9, age_range_display='4-9 years',
         address='Kilbogget Park, Cabinteely, Co. Dublin',
         website_url='https://www.foxcabgaa.ie/'),

    # --- Stepaside ---
    dict(company_name='Stars of Erin GAA', category='GAA',
         description='Juvenile GAA training at the Stepaside all-weather pitch.',
         class_types=['GAA Juvenile Academy'], days_of_week=['Monday', 'Thursday'],
         address='Stepaside All Weather Pitch, Stepaside, Dublin 18',
         website_url='https://www.starsoferin.ie/'),
    dict(company_name='MorningStar Dojo - Stepaside', category='Martial Arts',
         description='Kids karate classes at Gaelscoil Shliabh Rua, Ballyogan Road (the same '
                      'business also runs at ETNS Cherrywood).',
         class_types=['Kids Karate'], minimum_age=5, age_range_display='5+ years',
         address='Gaelscoil Shliabh Rua, Ballyogan Road, Dublin 18',
         website_url='https://www.facebook.com/MorningStarDojo'),

    # --- Deansgrange ---
    dict(company_name='The Martial Arts Academy', category='Martial Arts',
         description='Martial arts classes for kids and teens.',
         class_types=['Kids Martial Arts'], minimum_age=4, maximum_age=10,
         age_range_display='4-10 years (teens 12-17 also offered)',
         address='Unit 1, Block E, Deansgrange Business Park, Deansgrange, Co. Dublin',
         website_url='https://www.themartialartsacademy.com/'),

    # --- Loughlinstown ---
    dict(company_name='SuperSonic Trampoline Club', category='Gymnastics',
         description='Trampoline club with a toddler area for under-3s.',
         class_types=['Trampoline'], minimum_age=4, age_range_display='4+ (toddler area for under-3s too)',
         address='Loughlinstown Leisure Centre, Loughlinstown Drive, Dublin 18, A96 XP60',
         website_url='https://www.supersonictc.ie/'),
    dict(company_name='Tanden Shotokan Karate', category='Martial Arts',
         description='Shotokan karate classes at Loughlinstown Leisure Centre.',
         class_types=['Karate'],
         address='Loughlinstown Leisure Centre, Loughlinstown Drive, Dublin 18',
         phone_number='+353 87 989 3765'),

    # --- Palmerstown ---
    dict(company_name='Ruth Shine School of Dance - Palmerstown', category='Dance',
         description='Long-running (30+ years) dance school for toddlers through adults.',
         class_types=['Dance Classes'], age_range_display='Toddlers-adult',
         address='Parish Centre, Palmerstown village, Dublin 20',
         website_url='https://www.ruthshineschoolofdance.com/'),
    dict(company_name='Wojtek Potaszkin Dance Academy', category='Dance',
         description='Dance academy for children, teens and adults, beginner to competitive level.',
         class_types=['Dance Classes'], age_range_display='Children-adult',
         address='Unit 1, Old Lucan Road, Palmerstown Lower, Dublin 20',
         website_url='https://www.wojtekdance.com/'),
    dict(company_name="St Patrick's GAA - Palmerstown", category='GAA',
         description='GAA academy/nursery for young children.',
         class_types=['GAA Nursery'], maximum_age=6, age_range_display='Under 6',
         address='St Pats Clubhouse, Glenaulin Green, Redcowfarm, Palmerstown, D20 A292',
         website_url='https://www.stpatricksgaa.ie/teams'),

    # --- Inchicore ---
    dict(company_name="St Patrick's Athletic FC", category='Football',
         description='Football academy and Easter/summer camps, plus a year-round schoolboy/girl '
                      'academy via Crumlin United affiliation.',
         class_types=['Football Academy', 'Camps'], minimum_age=5, maximum_age=13, age_range_display='5-13 years',
         address='125 Emmet Road, Inchicore, Dublin 8',
         website_url='https://www.stpatsfc.com/'),
    dict(company_name='Karen Byrne School of Dance', category='Dance',
         description='Dance school covering Baby Ballroom, Latin & Ballroom, and Acro/Lyrical/Jazz.',
         class_types=['Ballroom', 'Latin', 'Acro/Lyrical/Jazz'], minimum_age=3, maximum_age=17,
         age_range_display='3-17 years',
         address='Bluebell Business Park, Unit 6 Old Naas Road, Inchicore, Dublin 8',
         website_url='https://www.karenbyrnestudios.com/'),
    dict(company_name='Marian Lennon School of Ballet - Inchicore', category='Dance',
         description='Ballet classes for all ages plus modern dance for 7+, Saturdays.',
         class_types=['Ballet', 'Modern Dance'], minimum_age=7, age_range_display='All ages (modern dance 7+)',
         days_of_week=['Saturday'],
         address="Inchicore Community Sports Centre, St Michael's Estate, Inchicore, Dublin 8",
         website_url='https://www.marianlennonschoolofballet.com/'),
    dict(company_name='CIE Boxing Club', category='Martial Arts',
         description='Boxing club welcoming kids and juniors.',
         class_types=['Junior Boxing'],
         address='Granite Terrace, Inchicore, Dublin 8, D08 X525',
         website_url='https://www.cieboxingclub.org/'),
    dict(company_name='Alonchai Muay Thai & Boxing', category='Martial Arts',
         description='Muay Thai and boxing gym in Inchicore.',
         class_types=['Muay Thai', 'Boxing'],
         address='Unit 14D, Goldenbridge Industrial Estate, Tyrconnell Road, Inchicore, D08 R768',
         website_url='https://www.alonchai.com/'),
    dict(company_name='Little Beras', category='Parent-and-toddler',
         description='Baby and toddler group at BERA Hall.',
         class_types=['Baby & Toddler Group'], maximum_age=4, age_range_display='0-4 years',
         address='BERA Hall, Connolly Avenue, Bulfin Estate, Inchicore, Dublin 8',
         website_url='https://www.littleberas.com/'),

    # --- Clonsilla ---
    dict(company_name="St Peregrine's GAA", category='GAA',
         description='GAA nursery/academy, plus camps up to age 12.',
         class_types=['GAA Nursery/Academy'], minimum_age=4, age_range_display='4+ years',
         address='Blakestown Road, Clonsilla, Dublin 15',
         website_url='https://www.stperegrines.ie/'),
    dict(company_name='Erin go Bragh GAA', category='GAA',
         description='GAA nursery; the same club also runs a session out of Ongar Community Centre.',
         class_types=['GAA Nursery'], minimum_age=4, maximum_age=7, age_range_display='4-7 years',
         address='Clubhouse adjacent to Mary Mother of Hope NS, Clonsilla, Dublin 15',
         website_url='https://www.ongarcc.ie/classes/erin-go-bragh'),
    dict(company_name='Coolmine Swim Club', category='Swimming',
         description='Competitive swim club with squad levels from entry to senior.',
         class_types=['Swim Squad'], age_range_display='Squad-based: Sharks (entry), Dolphins, Development, Seniors',
         address='Coolmine Sports & Leisure Centre, Grove Road, Clonsilla, Dublin 15, D15 XW52',
         website_url='https://uk.gomotionapp.com/team/clsc'),
    dict(company_name='Turtle Tots - Coolmine/Clonsilla', category='Swimming',
         description='Baby swimming classes for babies from 3 months to 4.5 years.',
         class_types=['Baby Swimming'], minimum_age=0.25, maximum_age=4.5, age_range_display='3mo-4.5yrs',
         address='Coolmine Sports & Leisure Centre, Grove Road, Clonsilla, Dublin 15',
         website_url='https://www.turtletots.ie/venue/baby-swimming-coolmine-sports-leisure-centre'),
    dict(company_name='Kantanni Karate-Do - Coolmine', category='Martial Arts',
         description='Karate classes, Tuesday and Saturday sessions.',
         class_types=['Karate'], days_of_week=['Tuesday', 'Saturday'],
         address='Coolmine Sports & Leisure Centre, Grove Road, Clonsilla, Dublin 15',
         website_url='https://www.kantanni-karate.ie/'),

    # --- Ongar ---
    dict(company_name='K-Star Academy - Ongar', category='Dance',
         description='Dance studio classes at Ongar Community Centre.',
         class_types=['Dance Classes'], minimum_age=4, maximum_age=18, age_range_display='4-18 years',
         address='Ongar Community Centre, 15 Ongar Road, Ongar Village, Dublin 15, D15 VR72',
         website_url='https://k-star-academy.classforkids.io/venue/2/ongar-community-centre'),
    dict(company_name='Master Joe Taekwondo - Ongar', category='Martial Arts',
         description='Taekwondo classes at Ongar Community Centre, Monday sessions split by age.',
         class_types=['Taekwondo'], minimum_age=6, maximum_age=16, age_range_display='6-9 and 10-16 years (Mon)',
         days_of_week=['Monday'],
         address='Ongar Community Centre, Dublin 15',
         website_url='https://www.joetaekwondo.com/'),
    dict(company_name='Fusion Elite All Star Cheer & Dance', category='Dance',
         description='Cheer and dance classes for school-age girls at Ongar Community Centre.',
         class_types=['Cheer', 'Dance'],
         address='Ongar Community Centre, Dublin 15',
         website_url='https://www.ongarcc.ie/childrens-activities-at-ongar-community-centre'),
    dict(company_name='Ongar Chasers Basketball Club', category='Basketball',
         description='Basketball club for children through adult.',
         class_types=['Basketball'], minimum_age=4, age_range_display='4+ years',
         address='Ongar Community Centre / HETSS outdoor courts, Dublin 15',
         website_url='https://www.ongarchasers.com/'),
    dict(company_name='Clare Connolly Dance & Ballet School', category='Dance',
         description='Dance and ballet classes at Ongar Community Centre.',
         class_types=['Ballet', 'Dance'], minimum_age=2, age_range_display='2+ years',
         address='Ongar Community Centre, Dublin 15',
         website_url='https://www.ongarcc.ie/childrens-activities-at-ongar-community-centre'),
    dict(company_name='Anne Walsh School of Irish Dancing', category='Dance',
         description='Irish dancing classes at Ongar Community Centre.',
         class_types=['Irish Dancing'],
         address='Ongar Community Centre, Dublin 15',
         website_url='https://www.ongarcc.ie/childrens-activities-at-ongar-community-centre'),
    dict(company_name='Little Kickers - Ongar', category='Football',
         description='Early-years football classes, Sunday mornings.',
         class_types=['Football Classes'], days_of_week=['Sunday'],
         address='Ongar Community Centre, Dublin 15',
         website_url='https://www.ongarcc.ie/'),
    dict(company_name='KidsComp - Ongar', category='STEM',
         description='Coding classes for kids.',
         class_types=['Coding'], minimum_age=6, age_range_display='6+ years',
         address='Ongar Community Centre, Dublin 15',
         website_url='https://www.kidscomp.ie/'),

    # --- Hartstown ---
    dict(company_name='Fit Kids/Fit Teens (FKFT) - Hartstown', category='Dance',
         description='Hip hop/dance fitness classes for kids, Tuesdays.',
         class_types=['Dance Fitness'], minimum_age=3, maximum_age=12, age_range_display='3-6 and 7-12 years',
         days_of_week=['Tuesday'],
         address='Hartstown Sport & Leisure Community Centre, Hartstown Road, Dublin 15, D15 CY60',
         website_url='https://www.fkft.ie/'),
    dict(company_name='Power Academy of Irish Dance - Hartstown', category='Dance',
         description='Irish dancing classes from age 2 through adult.',
         class_types=['Irish Dancing'], minimum_age=2, age_range_display='2-adult',
         address='Hartstown Sport & Leisure Community Centre, Hartstown Road, Dublin 15',
         website_url='https://www.powerirish.com/'),
    dict(company_name='Dance Fusion Empire - Hartstown', category='Dance',
         description='Freestyle, slowdance, lyrical and acro dance classes, Mondays.',
         class_types=['Freestyle', 'Lyrical', 'Acro'], minimum_age=4, maximum_age=21, age_range_display='4-21 years',
         days_of_week=['Monday'],
         address='Hartstown Sport & Leisure Community Centre, Hartstown Road, Dublin 15',
         website_url='https://www.hartstowncc.ie/dance-classes'),

    # --- Corduff ---
    dict(company_name='Corduff Karate Club', category='Martial Arts',
         description='Karate club founded 1992, with Beginner/Intermediate/Advanced levels.',
         class_types=['Karate'],
         address='Corduff Sports Centre, Blackcourt Road, Corduff, Dublin 15, D15 T861',
         website_url='https://www.corduffsportscentre.com/class-category/community'),

    # --- Glasnevin ---
    dict(company_name='Na Fianna GAA (CLG Na Fianna)', category='GAA',
         description='GAA nursery for children born 2019-2022.',
         class_types=['GAA Nursery'], minimum_age=4, maximum_age=6, age_range_display='4-6 years',
         address='St Mobhi Road, Glasnevin, Dublin 9, D09 AY09',
         website_url='https://clgnafianna.ie/club-information/nursery'),
    dict(company_name='Glasnevin Lawn Tennis Club', category='Tennis',
         description='Junior and intermediate tennis sections.',
         class_types=['Junior Tennis'], maximum_age=18,
         age_range_display='Under 14 (Junior), 14-18 (Intermediate)',
         address='Ballymun Road, Glasnevin, Dublin 9, D09 DR76',
         website_url='https://www.glasnevintennis.com/junior-tennis'),
    dict(company_name='Glasnevin FC (The Diggers)', category='Football',
         description='Football kindergarten and academy programme through to schoolboys/girls U16.',
         class_types=['Kindergarten', 'Academy'],
         age_range_display='U4/5 (Kindergarten), U6/7 (Academy), U8-U16 (Schoolboys/girls)',
         address='Albert College Park, Ballymun Road, Glasnevin, Dublin 9, D09 A4N8',
         website_url='https://www.glasnevinfc.ie/'),
    dict(company_name='Artzone - Glasnevin', category='Arts and crafts',
         description="Children's art classes at Na Fianna GAA Club, a separate venue from "
                      "Artzone's Dundrum/Malahide rows.",
         class_types=['Art Classes'],
         address='Na Fianna GAA Club, Glasnevin, Dublin 9',
         website_url='https://artzone.classforkids.io/venue/23/na-fianna-gaa-club-glasnevin'),
    dict(company_name='PlayAct Drama School - Glasnevin', category='Drama',
         description='Drama classes for juniors, a separate venue from PlayAct\'s Inchicore/'
                      'Terenure/Sandymount/Dun Laoghaire rows.',
         class_types=['Drama Classes'], minimum_age=5, maximum_age=7, age_range_display='5-7 years',
         address='Glasnevin Educate Together NS, Griffith Avenue, Glasnevin, D11 A2YT',
         website_url='https://playact.classforkids.io/camp/6'),
    dict(company_name='Glasnevin Academy of Music', category='Music',
         description='Music academy and tuition.',
         class_types=['Music Lessons'],
         address='210 Botanic Avenue, Dublin 9, D09 FN70',
         website_url='https://www.goldenpages.ie/glasnevin-academy-of-music-dublin-D09'),
    dict(company_name='Playright Music Ltd - Glasnevin', category='Music',
         description='Introduction to Piano lessons for children.',
         class_types=['Piano Lessons'],
         address='Glasnevin Avenue, Dublin 9',
         website_url='https://www.playrightmusicltd.com/piano-lessons-glasnevin'),
    dict(company_name='Phibsboro Chess Club', category='Other',
         description="Junior chess coaching and tournaments; despite the name, the club's "
                      'confirmed venue is in Glasnevin, not Phibsborough.',
         class_types=['Chess Club'], age_range_display='Beginner-2300+ (juniors tournament held)',
         address='Clareville Community Centre, Claremont Lawns, Glasnevin, D11 F8K1',
         website_url='https://www.phibsborochessclub.com/'),
    dict(company_name='DCU Sport Summer Camps - Glasnevin', category='Camps',
         description='Summer camps covering soccer, dance, basketball, GAA, rock climbing and arts & crafts.',
         class_types=['Summer Camp'], minimum_age=4, maximum_age=15, age_range_display='4-15 years',
         address='DCU Glasnevin Campus, Dublin 9',
         website_url='https://www.dcu.ie/dcusport'),

    # --- Phibsborough ---
    dict(company_name='Miss Eileene Ballet', category='Dance',
         description="Ballet classes at All Saint's Church Hall.",
         class_types=['Ballet'], minimum_age=3, maximum_age=5, age_range_display='3-5 years (plus older girls class)',
         address="All Saint's Church Hall, 30 Phibsborough Road, Dublin 7",
         website_url='https://www.familyfun.ie/miss-eileene-ballet-classes-dublin'),
    dict(company_name='Phibsboro Library - Toddler Storytime', category='Parent-and-toddler',
         description='Toddler storytime, second Tuesday of the month.',
         class_types=['Toddler Storytime'], age_range_display='Toddlers',
         term_structure='Drop-in', start_time='11:30',
         address='Phibsboro Library, Blacquiere Bridge, off North Circular Road, Dublin 7',
         website_url='https://www.dublincity.ie/events/toddler-storytime-phibsboro-library'),
    dict(company_name='Livingi Club Phibsboro', category='Martial Arts',
         description='Kids jiujitsu classes.',
         class_types=['Jiujitsu'],
         address='Unit 2 & 3, Crossguns Business Park, Royal Canal Bank, Phibsborough, Dublin 7',
         website_url='https://www.clublivingi.com/'),
    dict(company_name='Taking Flight - Aerial Arts', category='Gymnastics',
         description='Aerial arts classes for kids and teens; summer camps confirmed for ages 7-17.',
         class_types=['Aerial Arts'], minimum_age=7, maximum_age=17, age_range_display='7-17 years (camps)',
         address='Unit 4, Cross Guns Business Park, Royal Canal Bank, Phibsborough, Dublin 7',
         website_url='https://www.facebook.com/takingflightdublin'),

    # --- Marino ---
    dict(company_name='St Vincents GAA', category='GAA',
         description='Large GAA club with nursery through underage sections (~1,000 boys and girls).',
         class_types=['GAA Nursery/Underage'],
         address='Páirc Naomh Uinsionn, Malahide Road, Marino, Dublin 3, D03 YX08',
         website_url='https://www.stvincentsgaa.ie/'),
    dict(company_name='Hombu Dojo Karate - Marino', category='Martial Arts',
         description='Kids karate classes, Tuesday afternoons.',
         class_types=['Kids Karate'], minimum_age=5, maximum_age=11, age_range_display='5-11 years',
         days_of_week=['Tuesday'], start_time='16:00', end_time='17:00',
         address='Carleton Hall, Marino Community Centre, 53a Shelmartin Avenue, Marino, Dublin 3',
         website_url='https://hombudojokarate.com/'),
    dict(company_name='Clontarf School of Music - Marino', category='Music',
         description='Pre-instrumental course for young beginners, plus piano, guitar, violin and singing.',
         class_types=['Music Lessons'],
         address="6b Saint Aidan's Park Road, Marino, Dublin 3",
         website_url='https://www.clontarfmusicschool.com/'),
    dict(company_name='Marino Music Studio', category='Music',
         description='Singing and guitar tuition.',
         class_types=['Music Lessons'],
         address="13 Saint Declan's Road, Marino, Dublin 3, D03 P960",
         website_url='https://www.goldenpages.ie/marino-music-studio-dublin-D03'),

    # --- Fairview ---
    dict(company_name='Belvedere FC', category='Football',
         description='Early-years football academy (Little Eagles), plus DDSL Schoolboys U8-U18.',
         class_types=['Little Eagles Academy'], minimum_age=3, maximum_age=7, age_range_display='3-7 years',
         address='Fairview Park / Clontarf Road Complex, Fairview, Dublin 3',
         website_url='https://www.belvederefc.ie/little-eagles-academy'),
    dict(company_name="St Joseph's/OCB GAA", category='GAA',
         description='Juvenile GAA section drawing from East Wall, North Wall, Ballybough, Fairview and Marino.',
         class_types=['GAA Juvenile'],
         address='Fairview Park, Clontarf Road, Fairview, Dublin 3',
         website_url='https://www.stjosephsocb.com/'),
    dict(company_name='SVJ Karate Club', category='Martial Arts',
         description='Karate club with free introductory classes for children and adults.',
         class_types=['Karate'],
         address="St. Joseph's Primary School, Fairview, Dublin 3",
         website_url='https://www.svjkarate.net/'),

    # --- Cabra ---
    dict(company_name='Naomh Fionnbarra GAA', category='GAA',
         description='GAA academy programme, sharing a site with Gaelscoil Bharra.',
         class_types=['GAA Academy'],
         address='Fassaugh Avenue, Cabra, Dublin 7',
         website_url='https://www.naomhfionnbarra.ie/'),
    dict(company_name='Bohemian FC Youths', category='Football',
         description='Early-years football academy ("Bohs Juniors"), Saturday mornings.',
         class_types=['Bohs Juniors'], minimum_age=4, maximum_age=7, age_range_display='4-7 years',
         days_of_week=['Saturday'], start_time='10:00', end_time='11:00',
         address='Inspire Fitness Centre astro pitches, Ratoath Road, Cabra West, Dublin 7, D07 V4KP',
         website_url='https://www.bohemianfcyouths.com/bohs-juniors'),
    dict(company_name='Inspire Splash Academy', category='Swimming',
         description='Kids swimming lessons at Inspire Fitness Centre.',
         class_types=['Kids Swimming'],
         address='Inspire Fitness Centre, Ratoath Road, Cabra West, Dublin 7, D07 V4KP',
         website_url='https://www.inspirefitnesscentre.com/'),

    # --- Raheny ---
    dict(company_name='Dublin School of Dance and Etiquette (Third Arabesque)', category='Dance',
         description='Dance classes from Baby Ballet through Grade 3+.',
         class_types=['Baby Ballet', 'Ballet'],
         address='Cara Hall, Raheny, Dublin 5',
         website_url='https://www.thirdarabesque.com/'),
    dict(company_name='Hombu Dojo Karate - Raheny', category='Martial Arts',
         description='Kids karate classes.',
         class_types=['Kids Karate'], minimum_age=5, maximum_age=11, age_range_display='5-11 years',
         address='All Saints Hall, Raheny, Dublin 5',
         website_url='https://hombudojokarate.com/'),
    dict(company_name="St Paul's Karate Club", category='Martial Arts',
         description="Karate club at St Paul's College.",
         class_types=['Karate'],
         address="St Paul's College, Raheny, Dublin 5",
         website_url='https://www.facebook.com/StPaulsKarate'),
    dict(company_name='Raheny GAA', category='GAA',
         description='GAA nursery for children from age 4.',
         class_types=['GAA Nursery'], minimum_age=4, age_range_display='4+ years',
         address='C.L.G Rath Éanna, 2 All Saints Drive, Raheny, D05 WF44',
         website_url='https://www.rahenygaa.ie/'),
    dict(company_name='Raheny United FC', category='Football',
         description='Early-years football academy (Raheny Rookies).',
         class_types=['Raheny Rookies Academy'], minimum_age=4, maximum_age=6, age_range_display='4-6 years',
         address="RSA Astro Pitch, St Anne's Park / All Saints Drive, Raheny",
         website_url='https://www.rahenyunited.ie/'),
    dict(company_name="St Anne's Park Tennis Club", category='Tennis',
         description='Junior tennis coaching plus a Tots Tennis programme.',
         class_types=['Junior Coaching', 'Tots Tennis'], minimum_age=8, maximum_age=11,
         age_range_display='8-11 years (plus Tots Tennis)',
         address='All Saints Road, Raheny, D05 X6Y3',
         website_url='https://www.stannesparktennis.com/'),
    dict(company_name='Raheny Piano School', category='Music',
         description='Piano lessons.',
         class_types=['Piano Lessons'],
         address='616 Howth Road, Dublin 5',
         website_url='https://www.facebook.com/rahenypianoschool'),
    dict(company_name='Raheny Shamrock Athletic Club', category='Athletics',
         description='Juvenile athletics section with a large waiting list.',
         class_types=['Juvenile Athletics'], age_range_display='U9-U16',
         address='Raheny, Dublin 5',
         website_url='https://www.rahenyshamrock.ie/'),
    dict(company_name='The Jam - Art & Drama', category='Arts and crafts',
         description='Art and drama sessions for kids at CARA Hall.',
         class_types=['Art & Drama'], minimum_age=8, maximum_age=13, age_range_display='8-13 years',
         address='CARA Hall, Raheny, Dublin 5'),

    # --- Donaghmede ---
    dict(company_name='Trinity Gaels GAA', category='GAA',
         description='GAA nursery (Grasshoppers) for children age 4-7.',
         class_types=['GAA Nursery'], minimum_age=4, maximum_age=7, age_range_display='4-7 years',
         address='Drumnigh, Donaghmede, Dublin 13',
         website_url='https://www.trinitygaels.ie/'),
    dict(company_name='Trinity Donaghmede FC', category='Football',
         description='Football academy through U18.',
         class_types=['Football Academy'], minimum_age=4, age_range_display='4+ years (Academy through U18)',
         address='Father Collins Park, Hole in the Wall Road, Donaghmede, Dublin 13',
         website_url='https://www.trinitydonaghmedefc.com/'),
    dict(company_name='Trinity Sports & Leisure Club', category='Swimming',
         description="Children's swimming lessons, all abilities.",
         class_types=["Children's Swimming Lessons"],
         address='Hole in the Wall Road, Donaghmede, Dublin 13, D13 X651',
         website_url='https://www.trinitysportsandleisure.ie/'),
    dict(company_name='Cormorant Swimming Club', category='Swimming',
         description='Competitive swimming club for age 7+.',
         class_types=['Competitive Swimming'], minimum_age=7, age_range_display='7+ years',
         address='Trinity Sports & Leisure Club, Hole in the Wall Road, Donaghmede',
         website_url='https://www.cormorantswimclub.ie/'),

    # --- Kilbarrack ---
    dict(company_name='Naomh Barróg GAA', category='GAA',
         description='GAA academy (Barróg Beaga) for children age 4-7.',
         class_types=['GAA Academy'], minimum_age=4, maximum_age=7, age_range_display='4-7 years',
         address='Kilbarrack Parade, Kilbarrack Upper, Dublin 5',
         website_url='https://www.naomhbarrog.ie/'),
    dict(company_name='Naomh Barróg Juniors Chess Club', category='Other',
         description='Junior chess club.',
         class_types=['Chess Club'],
         address='Kilbarrack Parade, Kilbarrack, Dublin 5',
         website_url='https://leinsterjuniorchess.wordpress.com/'),
    dict(company_name='Sean Gilligan Performing Arts - Kilbarrack', category='Drama',
         description='Performing arts classes covering drama, dance and music at Star Studios.',
         class_types=['Performing Arts'], minimum_age=3, age_range_display='3+ years',
         address="Star Studios, Kilbarrack Shopping Centre, Swan's Nest Road, Kilbarrack, Dublin 5, D05 PT86",
         website_url='https://www.seangparts.com/'),

    # --- Artane ---
    dict(company_name='Compound Martial Arts', category='Martial Arts',
         description='Martial arts classes for kids.',
         class_types=['Kids Martial Arts'], minimum_age=8, maximum_age=12, age_range_display='8-12 years',
         address='24 Butterly Business Park, Kilmore Road, Artane, Dublin 5',
         website_url='https://www.compoundmartialarts.com/'),
    dict(company_name="St. Paul's Artane FC", category='Football',
         description='Early-years football academy, Saturdays.',
         class_types=['Football Academy'], minimum_age=5, maximum_age=8, age_range_display='5-8 years',
         days_of_week=['Saturday'],
         address='Clubhouse Astropitch, Gracefield Avenue, Artane, Dublin 5',
         website_url='https://www.stpaulsartanefc.com/'),
    dict(company_name='Sean Gilligan Performing Arts - Artane', category='Drama',
         description='Performing arts classes, a separate venue from the Kilbarrack branch of the same company.',
         class_types=['Performing Arts'], minimum_age=3, maximum_age=13,
         age_range_display='3-13 years (Juniors/Intermediate)',
         address='Artane, Dublin 5',
         website_url='https://www.seangparts.com/artane'),
    dict(company_name='Elm Mount Chess Club', category='Other',
         description='Chess club for juniors and novices, Wednesday evenings.',
         class_types=['Chess Club'], days_of_week=['Wednesday'], start_time='19:30', end_time='21:00',
         address='Artane Beaumont Family Recreation Centre, Kilmore Road, Artane, Dublin 5',
         website_url='https://www.elmmountchess.com/'),
    dict(company_name='Rockfield Tennis Club', category='Tennis',
         description='Junior tennis coaching programme.',
         class_types=['Junior Coaching'],
         address='Rockfield Park, Beaumont, Dublin 5',
         website_url='https://www.rockfieldtennisclub.ie/'),

    # --- Coolock ---
    dict(company_name="Parnell's GAA Club", category='GAA',
         description='GAA nursery (Nippers), Saturday mornings.',
         class_types=['GAA Nursery'], minimum_age=4, maximum_age=7, age_range_display='4-7 years',
         days_of_week=['Saturday'],
         address='The Clubhouse, Main Street, Coolock, Dublin 5',
         website_url='https://www.parnellsgaa.ie/'),
    dict(company_name='Coolock Kenpo Karate Club', category='Martial Arts',
         description='Kenpo karate classes, part of the same chain as Ballinteer Kenpo Karate Club.',
         class_types=['Kenpo Karate'], minimum_age=5, maximum_age=15, age_range_display='5-15 years',
         address='Scout Hall, Coolock Village, Coolock, Dublin 5',
         website_url='https://www.irish-kenpo.com/'),
    dict(company_name='Bohemian FC Academy', category='Football',
         description='Small-sided games football programme.',
         class_types=['Small-Sided Games'], age_range_display='U8-U12',
         address='Oscar Traynor Centre, Oscar Traynor Road, Coolock, Dublin 17',
         website_url='https://www.bohemians.ie/'),
    dict(company_name='Astropark Coolock', category='Camps',
         description='Multi-activity summer camps.',
         class_types=['Summer Camp'], minimum_age=5, maximum_age=12, age_range_display='5-12 years',
         address='Oscar Traynor Road / Coolock Lane, Coolock, Dublin 17, D17 Y998',
         website_url='https://www.astropark.ie/'),
    dict(company_name='Olympus Dance & Music School', category='Dance',
         description='Preschool dance, Fitnastix gymnastics, and music/art classes.',
         class_types=['Preschool Dance', 'Gymnastics', 'Music', 'Art'],
         address='Unit 10C, Ringuard House, Malahide Industrial Estate, Greencastle Parade, Dublin 17',
         website_url='https://www.danceandmusic.ie/'),

    # --- Santry ---
    dict(company_name='Larkhill Karate Club', category='Martial Arts',
         description='Karate classes across Lions/Dragons/Panthers age groups.',
         class_types=['Karate'], minimum_age=4, maximum_age=15, age_range_display='4-15+ years',
         address='Unit 4, Santry Hall Industrial Estate, Santry, Dublin 9, D09 V409',
         website_url='https://www.larkhillkarate.ie/'),
    dict(company_name='Grange Gymnastics Club', category='Gymnastics',
         description='Gymnastics Ireland member club for toddlers through adults.',
         class_types=['Gymnastics'], age_range_display='Toddlers-adults',
         address='Unit 10D, Airways Industrial Estate, Boeing Road, Santry, Dublin 9',
         website_url='https://www.grangegymnastics.com/'),
    dict(company_name='Thunderstruck Stage School - Santry', category='Drama',
         description='Stage school classes covering dance and drama.',
         class_types=['Stage School'], minimum_age=2.5, maximum_age=19, age_range_display='2.5-19 years',
         address='Unit 5, Santry Hall Industrial Estate, Santry, Dublin 9'),
    dict(company_name='Starlights GFC', category='GAA',
         description='GAA nursery (Little Stars), Saturday mornings.',
         class_types=['GAA Nursery'], minimum_age=3, maximum_age=7, age_range_display='3-7 years',
         days_of_week=['Saturday'], start_time='10:00', end_time='11:00',
         address="St Pappan's Parochial Hall, Santry village, Dublin 9"),
    dict(company_name='First Swim - Santry/Northwood', category='Swimming',
         description='Baby and toddler swim lessons, a new branch of the same company as the Sandyford location.',
         class_types=['Baby Swimming'], minimum_age=0.2, maximum_age=3, age_range_display='10 weeks-3 years',
         address="Gulliver's Retail Park, Northwood, Santry, Dublin 9"),
    dict(company_name='Sportslink - Aqua Tots', category='Swimming',
         description='Parent and baby swim classes.',
         class_types=['Aqua Tots'], minimum_age=0.1, maximum_age=3, age_range_display='3-36 months',
         address='Furry Park, Swords Road, Santry, Dublin 9',
         website_url='https://www.sportslink.ie/classes'),

    # --- Finglas ---
    dict(company_name='Finglas Celtic FC', category='Football',
         description='Football academy, Friday evenings and Saturday mornings.',
         class_types=['Football Academy'], minimum_age=4, maximum_age=7, age_range_display='4-7 years',
         days_of_week=['Friday', 'Saturday'],
         address='Finglas Celtic FC, Kilshane Road, Finglas West, Dublin 11, D11 VX43',
         website_url='https://www.finglasceltic.com/'),
    dict(company_name='Kobukan Kobudo Renmei - Finglas', category='Martial Arts',
         description='Kobudo martial arts classes.',
         class_types=['Kobudo'], minimum_age=5, maximum_age=12, age_range_display='5-12 years',
         address='Meakstown Community Centre, Lanesborough Park, Finglas, Dublin 11'),
    dict(company_name='House of Swag - Finglas', category='Dance',
         description='Dance, drama and gymnastics classes, Mondays, a new branch of the same '
                      'company as House of Swag Swords.',
         class_types=['Dance', 'Drama', 'Gymnastics'], minimum_age=4, age_range_display='4+ years',
         days_of_week=['Monday'],
         address='2D Century Business Park, Finglas, Dublin 11, D11 VP46'),
    dict(company_name='Little Kickers - Meakstown/Finglas', category='Football',
         description='Early-years football classes, a new branch of Little Kickers Dublin & Meath.',
         class_types=['Football Classes'], minimum_age=1.5, maximum_age=8, age_range_display='18mo-8yrs',
         address='Meakstown Community Centre, Lanesborough Park, Dublin 11, D11 N23T'),
    dict(company_name='FKFT Dance School - Finglas', category='Dance',
         description='Dance classes, Mondays.',
         class_types=['Dance Classes'], minimum_age=3, maximum_age=18, age_range_display='3-18 years',
         days_of_week=['Monday'],
         address='W.F.T.R.A Hall, Finglas, Dublin 11',
         website_url='https://www.fkft.ie/'),

    # --- Ballymun ---
    dict(company_name='Axis Ballymun', category='Drama',
         description='Drama classes (Tuesdays/Fridays); Beldance Irish Dancing and En Pointe '
                      'Ballet also run at the venue.',
         class_types=['Drama', 'Irish Dancing', 'Ballet'], minimum_age=7, maximum_age=16, age_range_display='7-16 years',
         days_of_week=['Tuesday', 'Friday'],
         address='Axis, Main Street, Ballymun, Dublin 9, D09 Y9W0',
         website_url='https://www.axisballymun.ie/'),
    dict(company_name='Sport Taekwondo Ireland - Ballymun', category='Martial Arts',
         description='Taekwondo classes, Monday and Wednesday.',
         class_types=['Taekwondo'], minimum_age=5, age_range_display='5+ years',
         days_of_week=['Monday', 'Wednesday'],
         address='Trinity Comprehensive School, Ballymun Road, Dublin 11',
         website_url='https://www.sporttkdirl.com/'),
    dict(company_name='Ballymun Boxing Club', category='Martial Arts',
         description='Junior boxing sessions, Tuesday and Thursday evenings.',
         class_types=['Junior Boxing'], days_of_week=['Tuesday', 'Thursday'], start_time='18:00',
         address='Poppintree Community Sports Centre, Balbutcher Lane, Ballymun, Dublin 9, D09 N9X6'),
]

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args()

    secret = os.environ['SB_SECRET']
    print(f'{len(ROWS)} rows to insert.')

    if not args.confirm:
        print('\nDry run (pass --confirm to write). Sample:')
        for row in ROWS[:5]:
            print(f'  {row["company_name"]} [{row["category"]}] -- {row["address"]}')
        return

    inserted = []
    for i, row in enumerate(ROWS):
        payload = build_payload(row)
        try:
            result = insert_row(secret, payload)
            inserted.append(result)
            print(f'[{i+1}/{len(ROWS)}] Inserted id={result["id"]}: {row["company_name"]}')
        except Exception as e:
            print(f'[{i+1}/{len(ROWS)}] FAILED: {row["company_name"]}: {e}')

    with open('/Users/davidmacmahon/kids-class-directory-website/downloads/dublin_expansion_candidates_inserted.json', 'w') as f:
        json.dump(inserted, f, indent=2)
    print(f'\nInserted {len(inserted)}/{len(ROWS)} rows.')
    print('Next: run scripts/google_geocode_missing.py to fill in coordinates, then '
          'scripts/generate_business_pages.py && scripts/generate_landing_pages.py to publish.')


if __name__ == '__main__':
    main()
