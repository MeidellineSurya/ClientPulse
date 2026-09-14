-- Apply to existing ClientPulse projects before deploying the matching backend.
-- Adds the columns app/services/anomaly_detection.py's portfolio-wide
-- Isolation Forest writes alongside the deterministic composite score.
-- Both nullable: the single-account recompute endpoint has no portfolio
-- context to fit a model against, and a book too small to train on yet
-- also leaves these null (see anomaly_detection.MIN_TRAINING_ROWS).
begin;

alter table health_score
  add column if not exists anomaly_score numeric,
  add column if not exists is_anomaly boolean;

commit;
