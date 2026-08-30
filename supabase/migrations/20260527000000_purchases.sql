create table if not exists purchases (
  id              uuid primary key default gen_random_uuid(),
  ls_order_id     text not null unique,
  ls_product_id   text not null,
  ls_variant_id   text not null,
  plan            text not null check (plan in ('single', 'starter', 'full')),
  customer_email  text,
  status          text not null default 'active',
  metadata        jsonb,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index if not exists purchases_customer_email_idx on purchases (customer_email);

alter table purchases enable row level security;

-- Edge functions use service role key — no RLS policy needed for server-side access.
-- Public reads are blocked by default (no SELECT policy).
