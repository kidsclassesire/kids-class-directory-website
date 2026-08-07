-- Age backfill, edge cases left out of scripts/backfill_ages_from_display.py
-- (that script only auto-fills rows it can parse with high confidence; these 54
-- rows all had age_range_display text that needed a human judgment call).
--
-- Grouped by confidence -- please skim before running, especially Section 3.
-- Only ever sets minimum_age/maximum_age where both are currently null.
-- Run in the Supabase SQL editor.

-- ============================================================
-- Section 1: High confidence (same pattern family as the automated
-- script, just a token shape it didn't recognize)
-- ============================================================
UPDATE public.classes SET minimum_age = 0, maximum_age = 17 WHERE id = 1765; -- Olympian Gymnastics - Rathgar | 'Under 12, 13-17' -- "Under 12" (0-12) + "13-17" is a contiguous 0-17 band; just an unrecognized token shape
UPDATE public.classes SET minimum_age = 0, maximum_age = 17 WHERE id = 1778; -- Olympian Gymnastics - Milltown | 'Under 12, 13-17' -- same business/format as id=1765
UPDATE public.classes SET minimum_age = 5, maximum_age = 12 WHERE id = 1784; -- Alto School of Music - Ranelagh | '~5-12 years' -- "~5-12 years" -- the leading tilde is what broke the bare-range parser
UPDATE public.classes SET minimum_age = 0, maximum_age = 14 WHERE id = 1786; -- Swan Leisure - Crumlin | 'Baby-14 years' -- "Baby-14 years" read as 0 to 14
UPDATE public.classes SET minimum_age = 0, maximum_age = 12 WHERE id = 1762; -- Spraoi Forest School - Bushy Park | 'Under 4 to 12+' -- "Under 4 to 12+" -- the trailing "+" means the true max may be higher than 12

-- ============================================================
-- Section 2: Enumerations with a real gap (e.g. a baby group that separately
-- mentions a teen program at the same venue). Using only the low/toddler
-- band, which matches these rows' own category (Parent-and-toddler /
-- Developmental) -- the disconnected higher-age mention is dropped rather
-- than stretched into a misleading single range.
-- ============================================================
UPDATE public.classes SET minimum_age = 0, maximum_age = 3.0 WHERE id = 178; -- Aster Balbriggan | '0-6 months, 6-12 months, 1 year old, 2 year old, 3 year old, 8 year old, 9 year old, 10 year old'
UPDATE public.classes SET minimum_age = 0, maximum_age = 5.0 WHERE id = 189; -- Ballymun Library | '0-6 months, 6-12 months, 1 year old, 2 year old, 3 year old, 4 year old, 5 year old, 10 year old, 11 year old, 12 year old, 13 year old, 14 year old, 15 year old'
UPDATE public.classes SET minimum_age = 0, maximum_age = 3.0 WHERE id = 195; -- Blanchardstown Library | '0-6 months, 6-12 months, 1 year old, 2 year old, 3 year old, 12 year old, 13 year old, 14 year old, 15 year old'
UPDATE public.classes SET minimum_age = 0, maximum_age = 4.0 WHERE id = 232; -- Harold's Cross - Toddler Group / Lego Club - Dolphin's Barn Library | '0-6 months, 6-12 months, 1 year old, 2 year old, 3 year old, 4 year old, 6 year old, 7 year old, 8 year old, 9 year old, 10 year old, 11 year old, 12 year old'
UPDATE public.classes SET minimum_age = 0, maximum_age = 5.0 WHERE id = 261; -- Pearse St Toddler Group & Junior Book Club | '0-6 months, 6-12 months, 1 year old, 2 year old, 3 year old, 4 year old, 5 year old, 8 year old, 9 year old, 10 year old, 11 year old, 12 year old'
UPDATE public.classes SET minimum_age = 0, maximum_age = 5.0 WHERE id = 265; -- Raheny Library - Toddler Group and Junior Book Clubs | '0-6 months, 6-12 months, 1 year old, 2 year old, 3 year old, 4 year old, 5 year old, 10 year old, 11 year old, 12 year old'
UPDATE public.classes SET minimum_age = 0, maximum_age = 2.0 WHERE id = 299; -- Walkinstown Baby & Toddler Storytime / Book clubs | '0-6 months, 6-12 months, 1 year old, 2 year old, 5 year old, 6 year old, 7 year old, 8 year old, 9 year old, 10 year old, 11 year old'
UPDATE public.classes SET minimum_age = 0, maximum_age = 1.0 WHERE id = 359; -- Pregnancy/Post-Natal Pilates | '0-6 months, 6-12 months, 15 year old'
UPDATE public.classes SET minimum_age = 0, maximum_age = 5.0 WHERE id = 582; -- Tullow & Carlow Central Library | '0-6 months, 6-12 months, 1 year old, 2 year old, 3 year old, 4 year old, 5 year old, 12 year old, 13 year old, 14 year old'
UPDATE public.classes SET minimum_age = 0, maximum_age = 5.0 WHERE id = 613; -- Scariff Baby & Toddler Groups / Kids Book Club - Scariff Library | '0-6 months, 6-12 months, 1 year old, 2 year old, 3 year old, 4 year old, 5 year old, 9 year old, 10 year old, 11 year old, 12 year old'
UPDATE public.classes SET minimum_age = 0.5, maximum_age = 1.0 WHERE id = 662; -- Piccolo Play Village Yoga & Sensory classes | '6-12 months, 6 year old'
UPDATE public.classes SET minimum_age = 0, maximum_age = 3.0 WHERE id = 717; -- Ballybane Library - Toddler Group / Junior Book Club | '0-6 months, 6-12 months, 1 year old, 2 year old, 3 year old, 8 year old, 9 year old, 10 year old, 11 year old'
UPDATE public.classes SET minimum_age = 0, maximum_age = 4.0 WHERE id = 847; -- Drumlish Library - Toddler Group / Kids Book Club / Social Group | '0-6 months, 6-12 months, 1 year old, 2 year old, 3 year old, 4 year old, 7 year old, 8 year old, 9 year old, 10 year old, 11 year old, 12 year old, 13 year old, 14 year old, 15 year old'
UPDATE public.classes SET minimum_age = 0, maximum_age = 7.0 WHERE id = 963; -- Bunclody Library | '0-6 months, 6-12 months, 1 year old, 2 year old, 3 year old, 4 year old, 5 year old, 6 year old, 7 year old, 13 year old, 14 year old, 15 year old'
UPDATE public.classes SET minimum_age = 0, maximum_age = 5.0 WHERE id = 1143; -- Tullow & Carlow Central Library | '0-6 months, 6-12 months, 1 year old, 2 year old, 3 year old, 4 year old, 5 year old, 12 year old, 13 year old, 14 year old'

-- ============================================================
-- Section 3: Rough estimates from qualitative/shorthand text -- LOW
-- CONFIDENCE, please sanity-check before running (or edit the numbers).
-- The "U7"-style sports shorthand rows are read literally (U7 = age 7);
-- some clubs use a different convention (e.g. U7 = age 6) -- verify against
-- how the business itself uses the term.
-- ============================================================
UPDATE public.classes SET minimum_age = 3, maximum_age = 8 WHERE id = 58; -- Junior Einsteins Science Club (South Dublin) | 'Maternelle/Infant classes through Year 1 & 2 (early primary)' -- French "Maternelle" (nursery, ~3) through Irish "Year 1 & 2" (~7-8) -- rough translation
UPDATE public.classes SET minimum_age = 0, maximum_age = 5 WHERE id = 1769; -- Rathmines Library Toddler Group | 'Babies-preschool' -- "Babies-preschool" -- preschool typically ends ~4-5 in Ireland
UPDATE public.classes SET minimum_age = 2, maximum_age = 5 WHERE id = 1770; -- Christ Church Rathgar Parents & Toddlers | 'Preschool' -- "Preschool" alone -- typically ~2.5-5, rounded to whole numbers
UPDATE public.classes SET minimum_age = 4, maximum_age = 12 WHERE id = 1792; -- Knights of Éanna Chess Club | 'School-age' -- "School-age" -- read narrowly as primary-school age, not incl. secondary/teens
UPDATE public.classes SET minimum_age = 4, maximum_age = 12 WHERE id = 1809; -- The Music Academy - Baldoyle | 'School-age' -- "School-age" -- same reading as id=1792
UPDATE public.classes SET minimum_age = 4, maximum_age = 17 WHERE id = 1796; -- Summit Judo/Jiu-Jitsu Academy | '4-7, 8-12, teens' -- "4-7, 8-12, teens" -- "teens" extended to 17 (contiguous with the 4-12 bands)
UPDATE public.classes SET minimum_age = 4, maximum_age = 17 WHERE id = 1801; -- Howth Yacht Club | 'Kids and teens' -- "Kids and teens" -- broad, low confidence
UPDATE public.classes SET minimum_age = 1, maximum_age = 3 WHERE id = 1804; -- Howth Library - Toddler Time | 'Toddlers' -- "Toddlers" -- standard toddler band
UPDATE public.classes SET minimum_age = 1, maximum_age = 3 WHERE id = 1868; -- Phibsboro Library - Toddler Storytime | 'Toddlers' -- "Toddlers" -- standard toddler band
UPDATE public.classes SET minimum_age = 4, maximum_age = 12 WHERE id = 1805; -- Sutton Dinghy Club | 'Children' -- "Children" alone -- very broad, low confidence
UPDATE public.classes SET minimum_age = 1, maximum_age = 6 WHERE id = 1819; -- Rush Multipurpose Youth Facility | 'Young children' -- "Young children" -- broad, low confidence
UPDATE public.classes SET minimum_age = 7, maximum_age = 18 WHERE id = 1817; -- Rush Athletic FC (RAFC) | 'U7-U18' -- "U7-U18" sports-club shorthand, read literally as ages 7-18 -- VERIFY, conventions vary
UPDATE public.classes SET minimum_age = 4, maximum_age = 16 WHERE id = 1860; -- Glasnevin FC (The Diggers) | 'U4/5 (Kindergarten), U6/7 (Academy), U8-U16 (Schoolboys/girls)' -- "U4/5, U6/7, U8-U16" read literally -- VERIFY
UPDATE public.classes SET minimum_age = 9, maximum_age = 16 WHERE id = 1888; -- Raheny Shamrock Athletic Club | 'U9-U16' -- "U9-U16" read literally -- VERIFY
UPDATE public.classes SET minimum_age = 8, maximum_age = 12 WHERE id = 1904; -- Bohemian FC Academy | 'U8-U12' -- "U8-U12" read literally -- VERIFY
UPDATE public.classes SET minimum_age = 2 WHERE id = 1763; -- Isabelle Ashe Dance Studios - Rathgar | 'From age 2' -- "From age 2" -- no stated upper bound, so only minimum_age is set
UPDATE public.classes SET minimum_age = 2 WHERE id = 1779; -- Isabelle Ashe Dance Studios - Ranelagh | 'From age 2' -- "From age 2" -- no stated upper bound, so only minimum_age is set
UPDATE public.classes SET minimum_age = 2 WHERE id = 1799; -- Isabelle Ashe Dance Studios - Templeogue | 'From age 2' -- "From age 2" -- no stated upper bound, so only minimum_age is set

-- ============================================================
-- Left alone entirely (NOT included above) -- no confident inference
-- possible, or the text says there is no single fixed range:
--   id=3 (Wild by Nature Forest School): "All ages (family session)" -- spans everyone; equivalent to leaving null
--   id=4 (Dublin School of Music): "Children and adults, all ages and abilities" -- equivalent to leaving null
--   id=5 (Dublin School of Music): "Children and adults, all ages and abilities" -- equivalent to leaving null
--   id=6 (Dublin School of Music): "Children and adults, all ages and abilities" -- equivalent to leaving null
--   id=412 (Churchtown School of Music): "Children and adults, all ages and skill levels" -- equivalent to leaving null
--   id=1800 (Mezzo Music Academy - Terenure): "Babies-adult" -- spans everyone; equivalent to leaving null
--   id=1802 (Howth Music School): "Children and adults" -- spans everyone; equivalent to leaving null
--   id=1832 (Ruth Shine School of Dance - Palmerstown): "Toddlers-adult" -- spans everyone; equivalent to leaving null
--   id=1833 (Wojtek Potaszkin Dance Academy): "Children-adult" -- spans everyone; equivalent to leaving null
--   id=1908 (Grange Gymnastics Club): "Toddlers-adults" -- spans everyone; equivalent to leaving null
--   id=413 (Templeogue College Swim Pool): "Children (specific age bands assigned after assessment)" -- text itself says there is no single fixed range
--   id=1754 (Terenure College Swimming Pool): "Stage-based" -- swim stage/level, not an age signal
--   id=1775 (Dartry Health Club - Kids Swimming Lessons): "Levelled programme" -- swim stage/level, not an age signal
--   id=1791 (Gym Plus Rathfarnham - Swim Plus Academy): "Multi-level" -- swim stage/level, not an age signal
--   id=1843 (Coolmine Swim Club): "Squad-based: Sharks (entry), Dolphins, Development, Seniors" -- squad names, not an age signal
--   id=1865 (Phibsboro Chess Club): "Beginner-2300+ (juniors tournament held)" -- 2300+ looks like a chess ELO rating, NOT an age. Do not backfill.
-- ============================================================

