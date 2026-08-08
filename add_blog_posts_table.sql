-- Blog section (scripts/generate_blog_pages.py, admin.html's Blog tab) --
-- posts are authored in admin.html, written here as Markdown, and rendered
-- to static blog/*.html pages by the generator, same shape as `classes`
-- feeding scripts/generate_business_pages.py.
--
-- Run this once in the Supabase SQL editor.

create table if not exists public.blog_posts (
  id bigint generated always as identity primary key,
  slug text not null unique,
  title text not null,
  excerpt text not null default '',
  content_markdown text not null default '',
  featured_image_path text,
  author_name text not null default 'Kids Patch Team',
  status text not null default 'draft' check (status in ('draft', 'published')),
  published_at timestamptz,
  meta_description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.blog_posts enable row level security;

-- Public (anon key, used by scripts/generate_blog_pages.py and the homepage
-- teaser) can only ever see posts that are actually published -- drafts and
-- scheduled-but-not-yet-due posts stay invisible until published_at passes.
drop policy if exists "Anyone can read published posts" on public.blog_posts;
create policy "Anyone can read published posts" on public.blog_posts
  for select
  using (status = 'published' and published_at is not null and published_at <= now());

-- Admins (admin.html's Blog tab) can see/manage everything, drafts included.
drop policy if exists "Admins can view all posts" on public.blog_posts;
create policy "Admins can view all posts" on public.blog_posts
  for select
  using (exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email')));

drop policy if exists "Admins can insert posts" on public.blog_posts;
create policy "Admins can insert posts" on public.blog_posts
  for insert
  with check (exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email')));

drop policy if exists "Admins can update posts" on public.blog_posts;
create policy "Admins can update posts" on public.blog_posts
  for update
  using (exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email')))
  with check (exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email')));

drop policy if exists "Admins can delete posts" on public.blog_posts;
create policy "Admins can delete posts" on public.blog_posts
  for delete
  using (exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email')));

-- ============================================================
-- Storage bucket for featured images
-- ============================================================
insert into storage.buckets (id, name, public)
values ('blog-uploads', 'blog-uploads', true)
on conflict (id) do nothing;

drop policy if exists "Public can view blog uploads" on storage.objects;
create policy "Public can view blog uploads" on storage.objects
  for select
  using (bucket_id = 'blog-uploads');

drop policy if exists "Admins can manage blog uploads" on storage.objects;
create policy "Admins can manage blog uploads" on storage.objects
  for all
  using (
    bucket_id = 'blog-uploads'
    and exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email'))
  )
  with check (
    bucket_id = 'blog-uploads'
    and exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email'))
  );
