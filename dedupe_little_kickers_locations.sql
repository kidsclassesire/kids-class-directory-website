-- Little Kickers had 3 physical venues each listed as 3-8 separate `classes`
-- rows -- one row per age-group/time-slot at the exact same address, rather
-- than one row per business per location. This collapses each venue down to
-- a single `classes` row (keeping the lowest id as canonical) with the
-- combined age range and class types, and moves the per-slot detail (day,
-- time, age band) into `individual_classes`, one row per class -- matching
-- the "1 row per class" table added by portal_individual_classes.sql.
--
-- Run replace_individual_classes_time_split.sql BEFORE this script -- it adds
-- the start_time/end_time columns that the inserts below write to.
--
-- Run this once in the Supabase SQL editor. After running, re-run
-- scripts/generate_business_pages.py to regenerate the static pages,
-- sitemap.xml and business-index.json, then delete the now-orphaned
-- business/*.html files for the removed ids (35, 36, 38-44, 46, 47).

begin;

-- ---------------------------------------------------------------------
-- Venue 1: Firhouse Community Centre, Ballycullen Drive, Firhouse, Dublin 24
-- Canonical row: id 34. Duplicates merged: 35, 36.
-- ---------------------------------------------------------------------
insert into public.individual_classes (business_id, name, day, start_time, end_time, min_age, max_age)
values
  (34, 'Little Kicks (1.5-2.5 years)', 'Sunday', '09:00', '09:45', 1.5, 2.5),
  (34, 'Junior Kickers (2.5-3.5 years)', 'Sunday', '10:00', '10:45', 2.5, 3.5),
  (34, 'Mighty Kickers (3.5 years to 5th birthday)', 'Sunday', '11:00', '11:45', 3.5, 5);

update public.classes set
  minimum_age = 1.5,
  maximum_age = 5,
  age_range_display = '18 months to 5th birthday (Little Kicks, Junior Kickers, Mighty Kickers by age group)',
  class_types = ARRAY['Little Kicks (1.5-2.5 years)', 'Junior Kickers (2.5-3.5 years)', 'Mighty Kickers (3.5 years to 5th birthday)'],
  days_of_week = ARRAY['Sunday'],
  start_time = null,
  end_time = null,
  pricing_details = 'EUR57 per month on a rolling monthly membership (no fixed term), plus a one-off EUR33 registration fee which includes a kit. Multiple weekly class slots run at this venue for different age groups (Little Kicks, Junior Kickers, Mighty Kickers) -- check the venue link below for exact days and times.'
where id = 34;

delete from public.classes where id in (35, 36);

-- ---------------------------------------------------------------------
-- Venue 2: Rockford Manor Secondary School, Stradbrook Road, Blackrock, Co. Dublin
-- Canonical row: id 37. Duplicates merged: 38, 39, 40, 41, 42, 43, 44.
-- ---------------------------------------------------------------------
insert into public.individual_classes (business_id, name, day, start_time, end_time, min_age, max_age)
values
  (37, 'Little Kicks (1.5-2.5 years)', 'Saturday', '09:30', '10:15', 1.5, 2.5),
  (37, 'Junior Kickers (2.5-3.5 years)', 'Saturday', '10:30', '11:15', 2.5, 3.5),
  (37, 'Junior Kickers (2.5-3.5 years)', 'Saturday', '11:30', '12:15', 2.5, 3.5),
  (37, 'Mighty Kickers (3.5 years to 5th birthday)', 'Saturday', '12:30', '13:15', 3.5, 5),
  (37, 'Little Kicks (1.5-2.5 years)', 'Sunday', '09:15', '10:00', 1.5, 2.5),
  (37, 'Little Kicks (1.5-2.5 years)', 'Sunday', '10:00', '10:45', 1.5, 2.5),
  (37, 'Junior Kickers (2.5-3.5 years)', 'Sunday', '11:00', '11:45', 2.5, 3.5),
  (37, 'Mighty Kickers (3.5 years to 5th birthday)', 'Sunday', '12:00', '12:45', 3.5, 5);

update public.classes set
  minimum_age = 1.5,
  maximum_age = 5,
  age_range_display = '18 months to 5th birthday (Little Kicks, Junior Kickers, Mighty Kickers by age group)',
  class_types = ARRAY['Little Kicks (1.5-2.5 years)', 'Junior Kickers (2.5-3.5 years)', 'Mighty Kickers (3.5 years to 5th birthday)'],
  days_of_week = ARRAY['Saturday', 'Sunday'],
  start_time = null,
  end_time = null,
  pricing_details = 'EUR57 per month on a rolling monthly membership (no fixed term), plus a one-off EUR33 registration fee which includes a kit. Multiple weekly class slots run at this venue across Saturday and Sunday for different age groups (Little Kicks, Junior Kickers, Mighty Kickers) -- check the venue link below for exact days and times.'
where id = 37;

delete from public.classes where id in (38, 39, 40, 41, 42, 43, 44);

-- ---------------------------------------------------------------------
-- Venue 3: The Spawell Complex, Templeogue, Dublin
-- Canonical row: id 45. Duplicates merged: 46, 47.
-- ---------------------------------------------------------------------
insert into public.individual_classes (business_id, name, day, start_time, end_time, min_age, max_age)
values
  (45, 'Little Kicks (1.5-2.5 years)', 'Saturday', '09:15', '10:00', 1.5, 2.5),
  (45, 'Junior Kickers (2.5-3.5 years)', 'Saturday', '10:10', '10:55', 2.5, 3.5),
  (45, 'Mighty Kickers (3.5 years to 5th birthday)', 'Saturday', '10:10', '10:55', 3.5, 5);

update public.classes set
  minimum_age = 1.5,
  maximum_age = 5,
  age_range_display = '18 months to 5th birthday (Little Kicks, Junior Kickers, Mighty Kickers by age group)',
  class_types = ARRAY['Little Kicks (1.5-2.5 years)', 'Junior Kickers (2.5-3.5 years)', 'Mighty Kickers (3.5 years to 5th birthday)'],
  days_of_week = ARRAY['Saturday'],
  start_time = null,
  end_time = null,
  pricing_details = 'EUR57 per month on a rolling monthly membership (no fixed term), plus a one-off EUR33 registration fee which includes a kit. Multiple weekly class slots run at this venue for different age groups (Little Kicks, Junior Kickers, Mighty Kickers) -- check the venue link below for exact days and times.'
where id = 45;

delete from public.classes where id in (46, 47);

commit;
