-- Same issue as dedupe_little_kickers_locations.sql: these 9 businesses each
-- had one `classes` row per class type/age band at the exact same address,
-- rather than one row per business per location. This collapses each down to
-- a single `classes` row (lowest id kept as canonical) with the combined age
-- range and class types, and moves the per-class detail into
-- `individual_classes`, one row per class.
--
-- Run replace_individual_classes_time_split.sql BEFORE this script -- it adds
-- the start_time/end_time columns the inserts below write to.
--
-- Run this once in the Supabase SQL editor. After running, re-run
-- scripts/generate_business_pages.py && scripts/generate_landing_pages.py to
-- regenerate the static pages/sitemap/business-index.json, then delete the
-- now-orphaned business/*.html files for the removed ids (2, 23, 28, 29, 50,
-- 52, 53, 54, 56, 57, 59, 61, 62, 63, 67).

begin;

-- ---------------------------------------------------------------------
-- South Dublin Dance Academy, Tallaght Enterprise Centre, Main Road, Tallaght, Dublin 24
-- Canonical row: id 51. Duplicates merged: 52, 53, 54.
-- ---------------------------------------------------------------------
insert into public.individual_classes (business_id, name, min_age, max_age)
values
  (51, 'Ballet', 3, null),
  (51, 'Hip Hop', 5, 14),
  (51, 'Tap', 5, null),
  (51, 'Musical Theatre', 5, 12);

update public.classes set
  minimum_age = 3,
  maximum_age = null,
  age_range_display = '3 years to adult (Ballet, Hip Hop, Tap, Musical Theatre by class)',
  class_types = ARRAY['Ballet', 'Hip Hop', 'Tap', 'Musical Theatre'],
  category = 'Dance',
  description = 'Dance and stage-school classes for children, teens and adults, including Ballet (posture, coordination and technical foundation for all genres), Hip Hop (contemporary choreography and rhythm), Tap (rhythm and footwork), and Musical Theatre (singing, dancing and acting, culminating in an annual showcase performance).'
where id = 51;

delete from public.classes where id in (52, 53, 54);

-- ---------------------------------------------------------------------
-- Trojan Gymnastic Club, 7/8 Holly Avenue, Stillorgan Business Park, Blackrock, Co. Dublin
-- Canonical row: id 60. Duplicates merged: 61, 62, 63.
-- ---------------------------------------------------------------------
insert into public.individual_classes (business_id, name, min_age, max_age)
values
  (60, 'Mini Rock ''n'' Rollers', 3, 3),
  (60, 'Rock ''n'' Rollers', 4, 5),
  (60, 'Banana Splits', 6, 8),
  (60, 'Twisters', 8, 12);

update public.classes set
  minimum_age = 3,
  maximum_age = 12,
  age_range_display = '3 to 12 years (Mini Rock ''n'' Rollers, Rock ''n'' Rollers, Banana Splits, Twisters by age group)',
  class_types = ARRAY['Mini Rock ''n'' Rollers', 'Rock ''n'' Rollers', 'Banana Splits', 'Twisters'],
  description = 'Recreational gymnastics classes for children of all levels: Mini Rock ''n'' Rollers and Rock ''n'' Rollers introduce balance, coordination and basic shapes; Banana Splits builds bridge kick-overs, drop backs and round-offs; Twisters progresses towards walkovers, aerials and handsprings for those assessed as ready to advance.'
where id = 60;

delete from public.classes where id in (61, 62, 63);

-- ---------------------------------------------------------------------
-- Artzone, Taney Parish Centre, Taney Road, Dundrum, Dublin 14
-- Canonical row: id 27. Duplicates merged: 28, 29.
-- All three age groups run the same week, same Mon-Fri 10:00-13:00 slot, so
-- days_of_week/start_time/end_time are left as-is on the canonical row.
-- ---------------------------------------------------------------------
insert into public.individual_classes (business_id, name, day, start_time, end_time, min_age, max_age)
values
  (27, 'Junior Art Camp', 'Monday-Friday', '10:00', '13:00', 5, 6),
  (27, 'Intermediate Art Camp', 'Monday-Friday', '10:00', '13:00', 7, 8),
  (27, 'Senior Art Camp', 'Monday-Friday', '10:00', '13:00', 9, 13);

update public.classes set
  minimum_age = 5,
  maximum_age = 13,
  age_range_display = '5 to 13 years (Junior, Intermediate and Senior Art Camp by age group)',
  class_types = ARRAY['Junior Art Camp (5-6 years)', 'Intermediate Art Camp (7-8 years)', 'Senior Art Camp (9-13 years)'],
  description = 'Themed art camp covering drawing, painting, craft and visual arts curriculum activities for primary school children, run by qualified art teachers over a full week. Age-graded groups run concurrently at this venue: Junior Art Camp (5-6 years), Intermediate Art Camp (7-8 years) and Senior Art Camp (9-13 years).',
  booking_url = 'https://artzone.classforkids.io/venue/32/taney-parish-centre-dundrum',
  source_urls = ARRAY['https://artzone.classforkids.io/camp/796', 'https://artzone.classforkids.io/camp/797', 'https://artzone.classforkids.io/camp/798', 'https://artzone.classforkids.io/venue/32/taney-parish-centre-dundrum']
where id = 27;

delete from public.classes where id in (28, 29);

-- ---------------------------------------------------------------------
-- Kate Buckley School of Dance, Rathfarnham Educate Together National School, Loreto Avenue, Rathfarnham, Dublin 14
-- Canonical row: id 55. Duplicates merged: 56, 57.
-- ---------------------------------------------------------------------
insert into public.individual_classes (business_id, name, min_age, max_age)
values
  (55, 'Ballet', 3, null),
  (55, 'Hip Hop', 3, null),
  (55, 'Tap', 3, null);

update public.classes set
  minimum_age = 3,
  maximum_age = null,
  age_range_display = '3 years old to young adults (Ballet, Hip Hop, Tap by class)',
  class_types = ARRAY['Ballet', 'Hip Hop', 'Tap'],
  description = 'Dance classes for children and young adults, including Ballet (posture, coordination and technique, with optional RAD/ISTD exams), Hip-Hop (school''s own syllabus of routines and rhythm work) and Tap (ISTD technique across a wide age range, with optional exams).',
  pricing_details = 'EUR165 for 1 child taking 1 class per week over a 15-week term (2025-26 published rates). Discounted rates apply for multiple classes per week or multiple siblings: EUR225 (1 child, 2 classes), EUR270 (1 child, 3 classes), EUR300 (2 children, 1 class each), EUR380 (3 children, 1 class each).'
where id = 55;

delete from public.classes where id in (56, 57);

-- ---------------------------------------------------------------------
-- Doodlebox, Rua Red South Dublin Arts Centre, Blessington Road, Tallaght, Dublin 24
-- Canonical row: id 1. Duplicates merged: 2.
-- ---------------------------------------------------------------------
insert into public.individual_classes (business_id, name, day, min_age, max_age)
values
  (1, 'Doodle Bugs', 'Thursday & Saturday', 5, 8),
  (1, 'Doodle Buddies', 'Thursday & Saturday', 9, 12);

update public.classes set
  minimum_age = 5,
  maximum_age = 12,
  age_range_display = '5 to 12 years (Doodle Bugs 5-8, Doodle Buddies 9-12)',
  class_types = ARRAY['Doodle Bugs', 'Doodle Buddies'],
  description = 'Fun, inclusive art school classes for primary school children, run by a qualified art therapist, covering varied media and materials with an annual student exhibition. Doodle Bugs (5-8 years) and Doodle Buddies (9-12 years) run as separate age groups.'
where id = 1;

delete from public.classes where id in (2);

-- ---------------------------------------------------------------------
-- Dalkey Library Parent and Toddler Group, Dalkey Library, Dalkey, Co. Dublin
-- Canonical row: id 22. Duplicates merged: 23.
-- Not an age split -- the same group just meets twice a week, same time both days.
-- ---------------------------------------------------------------------
insert into public.individual_classes (business_id, name, day, start_time, end_time)
values
  (22, 'Parent and Toddler Group', 'Monday', '10:30', '11:15'),
  (22, 'Parent and Toddler Group', 'Friday', '10:30', '11:15');

update public.classes set
  days_of_week = ARRAY['Monday', 'Friday']
where id = 22;

delete from public.classes where id in (23);

-- ---------------------------------------------------------------------
-- SCD Leisure Tallaght (Tallaght Leisure Centre), Fortunestown Way, Tallaght, Dublin 24
-- Canonical row: id 49. Duplicates merged: 50.
-- ---------------------------------------------------------------------
insert into public.individual_classes (business_id, name, min_age, max_age)
values
  (49, 'Adult and Toddler Swim', 0.33, 5),
  (49, 'Children''s Swim Lessons', 3, null);

update public.classes set
  minimum_age = 0.33,
  maximum_age = null,
  age_range_display = '4 months and up (Adult & Toddler Swim 4mo-5yrs, Children''s Swim Lessons 3yrs+)',
  class_types = ARRAY['Adult and Toddler Swim', 'Children''s Swim Lessons'],
  parental_requirement = 'Varies by Age or Class',
  term_structure = null,
  description = 'Swimming programmes at Tallaght Leisure Centre''s pool: supervised parent-and-toddler swim sessions using floats and toys for water confidence and play, and structured children''s swimming lessons taught by qualified instructors for all ability levels, both with lifeguards on duty.',
  booking_url = 'https://www.tallaghtleisure.com/pool/swimming-lessons/',
  pricing_details = 'Adult and Toddler Swim: described by the centre as low-cost pay-as-you-go pool access, exact price not published online -- see centre''s pool timetable for current session times. Children''s Swim Lessons: minimum booking is 8 sessions with full payment required at time of booking, exact price not published online; parents/guardians are required to remain on site during lessons.',
  source_urls = ARRAY['https://www.tallaghtleisure.com/adult-and-toddler-swim/', 'https://www.sdcc.ie/en/services/sport-and-recreation/leisure-facilities/tallaght-leisure-centre/', 'https://www.tallaghtleisure.com/pool/swimming-lessons/childrens-swim-lessons/', 'https://www.tallaghtleisure.com/pool/swimming-lessons/']
where id = 49;

delete from public.classes where id in (50);

-- ---------------------------------------------------------------------
-- Junior Einsteins Science Club (South Dublin), Lycee Francais International Samuel Beckett, Foxrock Avenue, Newpark, Foxrock, Co. Dublin
-- Canonical row: id 58. Duplicates merged: 59.
-- Both sessions run the same 15:00-16:00 slot, so start_time/end_time are left as-is.
-- ---------------------------------------------------------------------
insert into public.individual_classes (business_id, name, day, start_time, end_time)
values
  (58, 'After-School Science Club (Maternelle/Infant Classes)', 'Monday', '15:00', '16:00'),
  (58, 'After-School Science Club (Year 1 & Year 2)', 'Thursday', '15:00', '16:00');

update public.classes set
  age_range_display = 'Maternelle/Infant classes through Year 1 & 2 (early primary)',
  class_types = ARRAY['After-School Science Club (Maternelle/Infant Classes)', 'After-School Science Club (Year 1 & Year 2)'],
  days_of_week = ARRAY['Monday', 'Thursday'],
  description = 'Hands-on after-school science club for early primary school children, using messy, high-energy experiments to build curiosity and early scientific thinking, run weekly during the school term inside the school. Separate weekly sessions run for Maternelle/Infant classes and Year 1 & Year 2 age groups.'
where id = 58;

delete from public.classes where id in (59);

-- ---------------------------------------------------------------------
-- De La Salle Palmerston FC (DLSP), Kirwan Park, Kilternan, Dublin 18
-- Canonical row: id 66. Duplicates merged: 67.
-- ---------------------------------------------------------------------
insert into public.individual_classes (business_id, name, min_age, max_age)
values
  (66, 'Daisy Pickers', 3, 4),
  (66, 'Minis (Under 6 to Under 12)', 6, 12);

update public.classes set
  minimum_age = 3,
  maximum_age = 12,
  age_range_display = '3 to 12 years (Daisy Pickers 3-4, Minis Under 6 to Under 12)',
  class_types = ARRAY['Daisy Pickers', 'Minis (Under 6 to Under 12)'],
  parental_requirement = 'Varies by Age or Class',
  description = 'Mini rugby sections for boys and girls at one of Leinster''s oldest and largest mini-youth clubs, with IRFU-certified, Garda-vetted coaches. Daisy Pickers introduces the very youngest children to basic movement and ball skills in a fun, non-contact format; Minis (Under 6 to Under 12) builds age-appropriate rugby skills and teamwork.',
  source_urls = ARRAY['https://en.wikipedia.org/wiki/De_La_Salle_Palmerston', 'https://www.instagram.com/dlspfcrugby/', 'https://grokipedia.com/page/de_la_salle_palmerston', 'https://ie.linkedin.com/company/de-la-salle-palmerston']
where id = 66;

delete from public.classes where id in (67);

commit;
