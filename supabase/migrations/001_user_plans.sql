-- ============================================================
-- Migration 001: user_plans table
-- Run this in the Supabase SQL editor for your project.
--
-- Monthly counter resets are handled by the backend on each
-- request (checks reset_date and resets if past due), so no
-- pg_cron or Supabase scheduled functions are required.
-- ============================================================

create table if not exists public.user_plans (
  user_id                  uuid primary key references auth.users(id) on delete cascade,
  plan_name                text not null default 'free'
                             check (plan_name in ('free', 'creator', 'pro')),
  analyses_used_this_month integer not null default 0,
  reset_date               date not null
                             default (date_trunc('month', now()) + interval '1 month')::date,
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now()
);

-- Index for fast user_id lookups (primary key already covers this,
-- but explicit index makes intent clear for future queries).
create index if not exists user_plans_user_id_idx on public.user_plans(user_id);

-- ── Row Level Security ───────────────────────────────────────
alter table public.user_plans enable row level security;

-- Users may read their own row (for the dashboard usage widget).
create policy "users_read_own_plan"
  on public.user_plans for select
  using (auth.uid() = user_id);

-- Service role (backend) bypasses RLS automatically — no insert/update
-- policies needed for server-side writes.

-- ── Atomic increment function (optional — backend uses direct update) ──
create or replace function public.increment_user_analyses(p_user_id uuid)
returns void
language sql
security definer
as $$
  update public.user_plans
  set analyses_used_this_month = analyses_used_this_month + 1,
      updated_at = now()
  where user_id = p_user_id;
$$;

-- ── updated_at trigger ───────────────────────────────────────
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger user_plans_updated_at
  before update on public.user_plans
  for each row execute function public.set_updated_at();
