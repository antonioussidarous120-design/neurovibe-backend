-- Migration 003: Add stripe_customer_id to user_plans
-- Run this in Supabase SQL Editor for project rjrtamwknibnczgnrvur

alter table public.user_plans
  add column if not exists stripe_customer_id text;

-- Index for fast webhook lookups by customer ID
create index if not exists user_plans_stripe_customer_id_idx
  on public.user_plans (stripe_customer_id)
  where stripe_customer_id is not null;
