-- ClientPulse — Supabase schema (tables only, no seed data)
-- Run this in the Supabase SQL editor, or via `supabase db push` / psql.

create extension if not exists "pgcrypto"; -- for gen_random_uuid()

-- =========================================================
-- agency
-- =========================================================
create table if not exists agency (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  created_at timestamptz not null default now()
);

-- =========================================================
-- account
-- =========================================================
create table if not exists account (
  id                       uuid primary key default gen_random_uuid(),
  agency_id                uuid not null references agency(id) on delete cascade,
  name                     text not null,
  contract_value_monthly   numeric(12, 2) not null default 0,
  contract_start_date      date not null,
  primary_contact_email    text,
  created_at               timestamptz not null default now()
);

create index if not exists idx_account_agency_id on account(agency_id);

-- =========================================================
-- signal_snapshot
-- Periodic (e.g. weekly) rollup of raw behavioral signals per account.
-- =========================================================
create table if not exists signal_snapshot (
  id                       uuid primary key default gen_random_uuid(),
  account_id               uuid not null references account(id) on delete cascade,
  period_start             date not null,
  period_end               date not null,
  avg_response_time_hours  numeric(6, 2) not null default 0,
  meetings_scheduled       integer not null default 0,
  meetings_cancelled       integer not null default 0,
  invoice_days_late        integer not null default 0,
  email_thread_count       integer not null default 0,

  constraint chk_signal_snapshot_period check (period_end >= period_start)
);

create index if not exists idx_signal_snapshot_account_id on signal_snapshot(account_id);
create index if not exists idx_signal_snapshot_period on signal_snapshot(account_id, period_start);

-- =========================================================
-- baseline
-- Rolling average/stddev per account per signal, used for drift detection.
-- =========================================================
create table if not exists baseline (
  id             uuid primary key default gen_random_uuid(),
  account_id     uuid not null references account(id) on delete cascade,
  signal_name    text not null,
  rolling_avg    numeric(10, 2),
  rolling_stddev numeric(10, 2),
  last_updated   timestamptz not null default now(),

  constraint uq_baseline_account_signal unique (account_id, signal_name)
);

create index if not exists idx_baseline_account_id on baseline(account_id);

-- =========================================================
-- health_score
-- Computed composite health score snapshots over time.
-- =========================================================
create table if not exists health_score (
  id               uuid primary key default gen_random_uuid(),
  account_id       uuid not null references account(id) on delete cascade,
  computed_at      timestamptz not null default now(),
  composite_score  numeric(5, 2) not null,
  trend_slope      numeric(8, 4) not null default 0
);

create index if not exists idx_health_score_account_id on health_score(account_id);
create index if not exists idx_health_score_computed_at on health_score(account_id, computed_at desc);

-- =========================================================
-- alert
-- =========================================================
create table if not exists alert (
  id                uuid primary key default gen_random_uuid(),
  account_id        uuid not null references account(id) on delete cascade,
  triggered_at      timestamptz not null default now(),
  signals_fired     jsonb not null default '[]'::jsonb,
  severity          text not null default 'medium',
  ai_brief          text,
  suggested_action  text,
  status            text not null default 'open',
  revision          bigint not null default 0 check (revision >= 0),

  constraint chk_alert_severity check (severity in ('low', 'medium', 'high', 'critical')),
  constraint chk_alert_status check (status in ('open', 'acknowledged', 'resolved'))
);

-- CREATE TABLE IF NOT EXISTS does not add new columns to an existing project.
-- Keep the canonical schema replayable as an upgrade as well as a fresh install.
alter table alert
  add column if not exists revision bigint not null default 0 check (revision >= 0);

-- Every alert mutation advances a database-owned revision. The scoring API
-- compares the revision it read before writing a generated brief, preventing
-- stale recomputes from overwriting status changes or human-edited evidence.
create or replace function public.bump_alert_revision()
returns trigger
language plpgsql
as $$
begin
  new.revision := old.revision + 1;
  return new;
end;
$$;

drop trigger if exists trg_alert_revision on alert;
create trigger trg_alert_revision
  before update on alert
  for each row execute function public.bump_alert_revision();

create index if not exists idx_alert_account_id on alert(account_id);
create index if not exists idx_alert_triggered_at on alert(triggered_at desc);
create index if not exists idx_alert_status on alert(status);

-- Deduplication must be enforced in PostgreSQL, not by a SELECT followed by
-- INSERT in the API: concurrent recomputes can otherwise create two active
-- alerts for the same account. Resolved alerts do not participate, so a later
-- deterioration episode can create a fresh row.
create unique index if not exists uq_alert_one_active_per_account
  on alert(account_id)
  where status in ('open', 'acknowledged');
