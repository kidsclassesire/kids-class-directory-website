-- Fixes logo_path/hosted_image_path so they work on GitHub Pages project sites.
-- The site is served at https://kidsclassesire.github.io/kids-class-directory-website/
-- (a subpath, not the domain root), so an absolute path like "/logos/x.png" resolves
-- against the domain root and 404s. A relative path ("logos/x.png") resolves against
-- the page's own location instead, which works both on GitHub Pages and locally.
-- Run this once in the Supabase SQL editor.

update public.classes
  set logo_path = ltrim(logo_path, '/')
  where logo_path is not null;

update public.classes
  set hosted_image_path = ltrim(hosted_image_path, '/')
  where hosted_image_path is not null;
