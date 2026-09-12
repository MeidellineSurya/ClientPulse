# Retention alert and brief module

The `retention_radar` package implements the deterministic alert boundary and the evidence-bound LLM brief that follows it. It does **not** calculate composite risk scores, write to Supabase, or contact clients. The FastAPI account and alert routes documented below expose database-backed portfolio and inbox data while keeping scoring deterministic.

## Contract

`evaluate_alert(...)` accepts chronological `HealthScore` snapshots and fires only when:

1. the latest composite risk crosses the configured threshold from below; and
2. the latest three composite-risk values are strictly worsening.

The returned `episode_key` can be stored with the alert row and passed back through `alerted_episode_keys` to make retries idempotent. Severity is `medium` from the configured threshold, `high` from `0.80`, and `critical` from `0.90`.

`build_alert(...)` is the integration entrypoint. It runs deterministic policy first and calls the brief provider only when an alert should exist. The LLM receives the authoritative risk, triggered signals, recent trend, account name, and monthly value. It never calculates the score.

```python
import os
from retention_radar import GroqBriefProvider, HealthScore, build_alert

provider = GroqBriefProvider(
    api_key=os.environ["GROQ_API_KEY"],
    model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
)

alert = build_alert(
    score_history,
    account_name="StudioCo",
    monthly_value=10_000,
    provider=provider,
    alerted_episode_keys=existing_episode_keys,
)
```

The provider requests JSON and the module validates exact fields, non-empty strings, driver count, and output lengths. Provider errors or malformed output fall back to a deterministic brief, so a demo never depends on LLM availability.

## Tests

From `backend/`:

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

The tests make no network calls and require no API key.

## Account and alert endpoints

All database-backed endpoints return `503` when Supabase is not configured.

- `GET /accounts` — alphabetized portfolio summaries with the latest score and active-alert count.
- `GET /accounts/{account_id}` — account metadata plus chronological score/signal history and newest-first alerts.
- `GET /alerts` — newest-first alert inbox; optionally filter with `?status=open|acknowledged|resolved`.
- `PATCH /alerts/{alert_id}` — update an alert to `acknowledged` or `resolved`.

Unknown account and alert IDs return `404`; invalid status values return FastAPI validation errors without touching Supabase.
