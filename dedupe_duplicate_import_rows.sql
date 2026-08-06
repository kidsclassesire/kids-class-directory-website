-- Different bug from dedupe_little_kickers_locations.sql /
-- dedupe_multi_class_venues.sql: these aren't one business split across
-- several class types -- they're the *same* listing imported twice (mostly
-- via totsspots.com, scraped on two different occasions), sharing the same
-- company_name and address with identical or near-identical content. Fix is
-- a plain dedup: keep the more complete/accurate row, delete the other. No
-- individual_classes rows needed since there's only ever been one class here.
--
-- Run this once in the Supabase SQL editor. After running, re-run
-- scripts/generate_business_pages.py && scripts/generate_landing_pages.py to
-- regenerate the static pages/sitemap/business-index.json, then delete the
-- now-orphaned business/*.html files for the removed ids (325, 1096, 930, 1029, 1163).

begin;

-- Claphandies -- rows 1028/1029 were byte-for-byte identical. Keep 1028.
delete from public.classes where id = 1029;

-- Play with Trayz -- rows 1162/1163 were byte-for-byte identical. Keep 1162.
delete from public.classes where id = 1163;

-- FREE Parent and Toddler Groups (Dundalk and Drogheda), Dundalk address
-- (Marshes Upper) -- rows 325/1097 differ only in source (325's website_url
-- was dead, 1097's is live). Keep 1097.
delete from public.classes where id = 325;

-- FREE Parent and Toddler Groups (Dundalk and Drogheda), Drogheda address
-- (St. Nicholas GFC, Rathmullan) -- rows 326/1096 are the same pair reversed
-- (1096's website_url was dead, 326's is live). Keep 326.
delete from public.classes where id = 1096;

-- Maia Purposeful Play -- rows 609/930 mostly match; 609 has an eircode 930
-- lacks, 930 has a slightly wider published age range (includes 5 year olds).
-- Keep 609, but pull in 930's wider age range and extra source_url before
-- deleting it.
update public.classes set
  age_range_display = '0-6 months, 6-12 months, 1 year old, 2 year old, 3 year old, 4 year old, 5 year old',
  source_urls = ARRAY['https://www.maiapurposefulplay.ie/', 'https://totsspots.com/listing/maia-purposeful-play/', 'https://totsspots.com/listing/maia-purposeful-play-sligo-kids-class/']
where id = 609;

delete from public.classes where id = 930;

commit;
