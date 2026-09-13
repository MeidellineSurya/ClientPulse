-- Apply to existing ClientPulse projects before deploying the matching backend.
-- email_thread_count was never part of the composite_score/alerting model
-- (see app/services/baseline_engine.py's RAW_SIGNAL_COLUMNS) and is no
-- longer computed or displayed anywhere, so the column is dropped rather
-- than left as dead data.
begin;

alter table signal_snapshot
  drop column if exists email_thread_count;

commit;
