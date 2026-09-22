-- ============================================================
-- Migration 002: extend user_plans with per-feature counters
-- Replaces the single analyses_used_this_month column with
-- separate counters for each tracked feature.
--
-- Run this in the Supabase SQL editor AFTER migration 001.
-- ============================================================

-- Add per-feature counter columns (safe to run multiple times)
alter table public.user_plans
  add column if not exists script_analyses_used    integer not null default 0,
  add column if not exists script_generations_used integer not null default 0,
  add column if not exists video_analyses_used     integer not null default 0;

-- Migrate existing data: copy old counter to script_analyses_used
update public.user_plans
set script_analyses_used = analyses_used_this_month
where script_analyses_used = 0
  and analyses_used_this_month > 0;

-- Drop the old single-counter column (remove if not yet added)
alter table public.user_plans
  drop column if exists analyses_used_this_month;

-- Update plan_name check constraint to match our three tiers
alter table public.user_plans
  drop constraint if exists user_plans_plan_name_check;

alter table public.user_plans
  add constraint user_plans_plan_name_check
  check (plan_name in ('free', 'creator', 'pro'));

-- ── Monthly reset RPC (called by the edge function) ───────────────────────────
create or replace function public.reset_monthly_usage()
returns void
language sql
security definer
as $$
  update public.user_plans
  set
    script_analyses_used    = 0,
    script_generations_used = 0,
    video_analyses_used     = 0,
    reset_date              = (date_trunc('month', now()) + interval '1 month')::date,
    updated_at              = now()
  where reset_date <= current_date;
$$;
