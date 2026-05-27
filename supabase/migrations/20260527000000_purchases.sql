create table if not exists purchases (
  id          uuid primary key default gen_random_uuid(),
  email       text not null,
  order_id    text not null unique,
  variant_id  text,
  plan        text not null check (plan in ('single', 'starter', 'full')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists purchases_email_idx on purchases (email);

alter table purchases enable row level security;

-- Edge functions use service role key — no RLS policy needed for server-side access.
-- Public reads are blocked by default (no SELECT policy).
