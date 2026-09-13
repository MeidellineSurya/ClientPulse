-- Apply to existing ClientPulse projects before deploying the matching backend.
-- Fail loudly rather than guessing which duplicate alert a human intended to keep.
begin;

alter table alert
  add column if not exists revision bigint not null default 0 check (revision >= 0);

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

do $$
begin
  if exists (
    select account_id
    from alert
    where status in ('open', 'acknowledged')
    group by account_id
    having count(*) > 1
  ) then
    raise exception
      'Cannot enforce one active alert per account: resolve existing duplicates first';
  end if;
end
$$;

create unique index if not exists uq_alert_one_active_per_account
  on alert(account_id)
  where status in ('open', 'acknowledged');

commit;
