-- Authenticate application users with Supabase Auth while keeping all
-- ClientPulse data behind the backend's service-role boundary.

begin;

create table if not exists public.agency_member (
  agency_id  uuid not null references public.agency(id) on delete cascade,
  user_id    uuid not null references auth.users(id) on delete cascade,
  role       text not null default 'member',
  created_at timestamptz not null default now(),

  constraint pk_agency_member primary key (agency_id, user_id),
  constraint uq_agency_member_user unique (user_id),
  constraint chk_agency_member_role check (role in ('member', 'admin'))
);

create index if not exists idx_agency_member_agency_id
  on public.agency_member(agency_id);

-- The browser only receives Supabase's anon key for Auth. It must never be able
-- to query application tables directly. No anon/authenticated policies are
-- created; the backend's service-role client bypasses RLS only after resolving
-- and enforcing the authenticated user's agency membership.
alter table public.agency enable row level security;
alter table public.agency_member enable row level security;
alter table public.account enable row level security;
alter table public.signal_snapshot enable row level security;
alter table public.baseline enable row level security;
alter table public.health_score enable row level security;
alter table public.alert enable row level security;

commit;
