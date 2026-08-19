-- بياع الحلويين — database schema
-- Run this once in your Supabase project's SQL editor
-- (Supabase dashboard -> SQL Editor -> New query -> paste -> Run).

create table if not exists users (
  id text primary key,
  name text not null,
  username text not null unique,
  role text not null default 'employee' check (role in ('admin', 'employee')),
  password_hash text not null,
  password_salt text not null,
  created_at bigint not null
);

create table if not exists suppliers (
  id text primary key,
  name text not null,
  phone text default '',
  notes text default '',
  created_by text,
  created_at bigint not null
);

create table if not exists transactions (
  id text primary key,
  supplier_id text not null references suppliers(id) on delete cascade,
  type text not null check (type in ('to', 'from')), -- 'to' = دفع, 'from' = استلم
  amount numeric not null,
  date text not null,
  note text default '',
  created_by text,
  created_at bigint not null
);

create table if not exists expenses (
  id text primary key,
  description text not null,
  category text default 'عام',
  amount numeric not null,
  date text not null,
  created_by text,
  created_at bigint not null
);

create table if not exists treasury (
  id text primary key,
  type text not null check (type in ('capital', 'cash')), -- رأس مال أساسي / سيولة نقدية
  amount numeric not null,
  date text not null,
  note text default '',
  created_by text,
  created_at bigint not null,
  source_transaction_id text references transactions(id) on delete cascade
);

create index if not exists idx_transactions_supplier on transactions(supplier_id);
create index if not exists idx_treasury_source on treasury(source_transaction_id);

-- ---------------------------------------------------------------------------
-- SECURITY NOTE (read this before going live):
--
-- This schema does NOT enable Row Level Security (RLS). With the public
-- anon key, anyone who has your Supabase URL + anon key can read and write
-- every row in every table above. That's fine for early development, but
-- NOT fine for a real deployment with real business data.
--
-- Recommended next step in Claude Code:
--   1. Migrate authentication to Supabase Auth (supabase.auth.signUp /
--      signInWithPassword) instead of the custom users table + client-side
--      hashing in src/lib/crypto.js.
--   2. Enable RLS on every table (`alter table X enable row level security;`)
--      and add policies scoped to `auth.uid()` so only logged-in users from
--      your own account can read/write your data.
-- ---------------------------------------------------------------------------
