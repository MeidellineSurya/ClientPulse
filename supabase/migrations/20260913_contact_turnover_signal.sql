-- Apply to existing ClientPulse projects before deploying the matching backend.
-- Adds the per-period contact-email column the new contact_changed signal
-- (app/services/baseline_engine.py) is derived from. Existing rows get
-- NULL, which derive_contact_changed treats as "unknown" rather than a
-- false-positive change.
begin;

alter table signal_snapshot
  add column if not exists primary_contact_email text;

commit;
