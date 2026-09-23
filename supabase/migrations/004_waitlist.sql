-- Migration 004: Waitlist table
-- Run in Supabase SQL Editor for project rjrtamwknibnczgnrvur

create table if not exists public.waitlist (
  id         uuid        primary key default gen_random_uuid(),
  email      text        unique not null,
  created_at timestamptz default now()
);

-- Anyone can insert (public waitlist form — no auth required)
alter table public.waitlist enable row level security;

create policy "public_insert_waitlist"
  on public.waitlist for insert
  with check (true);

-- Only service role can read (admin use only)
create policy "service_role_read_waitlist"
  on public.waitlist for select
  using (false);   -- anon/user roles blocked; service role bypasses RLS
