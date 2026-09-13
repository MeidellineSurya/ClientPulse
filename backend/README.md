# Retention alert and brief module

This branch implements the backend team's deterministic alert boundary and the evidence-bound LLM brief that follows it. It does **not** calculate composite risk scores, write to Supabase, expose HTTP routes, or contact clients.

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

## Gmail and Calendar ingestion

`POST /ingest/gmail-calendar/{account_id}` refreshes a narrowly scoped OAuth token,
reads Gmail **headers only** plus read-only Calendar events, computes the account's
response-time, thread-count, meeting, and cancellation signals, then upserts the
requested `signal_snapshot` period. Message bodies remain inaccessible because the
refresh token must carry only these scopes:

- `https://www.googleapis.com/auth/gmail.metadata`
- `https://www.googleapis.com/auth/calendar.readonly`

Configure `GOOGLE_AGENCY_ID`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and
`GOOGLE_REFRESH_TOKEN` in `backend/.env`. `GOOGLE_AGENCY_ID` hard-binds that mailbox
to one server-controlled agency; users in every other agency receive `404` before
Google is contacted. Obtain the refresh token with offline access and explicit consent
for exactly the two scopes above; do not commit or print it. The Gmail API forbids its
server-side `q` filter under `gmail.metadata`, so the backend paginates metadata and
filters exact participant addresses and UTC-normalized dates locally.

Example after configuring Google and Supabase credentials:

```bash
curl -X POST \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  "http://localhost:8000/ingest/gmail-calendar/ACCOUNT_UUID?period_start=2026-09-01&period_end=2026-09-07"
```

Both period bounds must be supplied together and `period_end` cannot precede
`period_start`. Omitting both defaults to the current Monday–Sunday week. OAuth
failures return `503`; Gmail/Calendar API failures return `502`; no snapshot is written
unless both Google reads succeed. The bearer token must identify a user assigned to
the account's agency; cross-agency account IDs return `404` before Google is contacted.

Calendar cancellation counts are observational: attendee-less cancelled items returned by
the exact contact query are attributed to that contact, but this polling route is not a
durable Calendar change ledger. Deletions Google no longer returns cannot be reconstructed
without persisting Calendar sync tokens and event identity state.
