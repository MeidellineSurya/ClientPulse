# ClientPulse

Behavioral churn early-warning tool for retainer-based agencies. Surfaces accounts
that are quietly drifting toward churn (slower replies, more cancellations, late
invoices) before the client says anything.

**🌐 Live:** [clientpulse-frontend.onrender.com](https://clientpulse-frontend.onrender.com)
(backend: [backend-ruddy-rho-34.vercel.app](https://backend-ruddy-rho-34.vercel.app))

> 🚧 Hackathon build. This repo is being scaffolded incrementally — see commit
> history for progress. Backend + frontend are live and verified end-to-end
> against a real Supabase project, behind real Supabase Auth (bearer tokens,
> agency-scoped access) — the app is no longer open access. Gmail/Calendar
> OAuth ingestion and CSV invoice import are both live-verified against real
> accounts/data, not just implemented. Groq-generated AI briefs are confirmed
> working in production. `app/services/scoring_engine.py` is confirmed as the
> sole alert-decision engine — see HANDOFF.md.
>
> Pitch, scoring formula, product decisions, and demo script: see
> [HANDOFF.md](./HANDOFF.md).

## Stack

- **Frontend:** React (Vite), TypeScript, React Router, Tailwind CSS, Recharts, Lucide —
  custom "Modernist" design system (flat, zero border-radius, ink-on-light-ground with
  a single red accent), not a component library
- **Backend:** FastAPI (Python 3.11+), Pydantic
- **Database:** Supabase (Postgres)
- **LLM:** Groq (`openai/gpt-oss-120b`)
- **Deploy:** frontend on Render (static site), backend on Vercel (Python ASGI
  serverless function) — switched from the original Vercel/Railway split
  after both Railway and Render's compute tier required a card on file;
  Render's static-site tier and Vercel's Python runtime needed neither

## Monorepo layout

```
clientpulse/
├── frontend/       # React (Vite) app
├── backend/        # FastAPI app
├── supabase/       # schema.sql + seed.sql
├── .env.example    # reference of all env vars used across the monorepo
└── README.md
```

## Running locally

1. **Database:** create a Supabase project, then run `supabase/schema.sql`,
   `supabase/seed.sql`, **and every file in `supabase/migrations/`** (in
   filename order) in its SQL Editor. The migrations aren't optional
   extras — the backend code already assumes their columns/constraints
   exist (`signal_snapshot.primary_contact_email`, `alert.revision`) and
   fails in ways that don't look like a missing migration: new alerts
   silently fail to insert, and `/score/recompute` reports them under
   `failed_account_ids` rather than a clear error.
   Create a user in Supabase Authentication and bind its UUID to the intended
   agency in `public.agency_member`; never accept an agency ID from the browser.
2. **Backend:**
   ```
   cd backend
   cp .env.example .env   # fill in SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, etc.
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```
3. **Frontend:**
   ```
   cd frontend
   cp .env.example .env.local   # API URL + public Supabase URL/anon key
   npm install
   npm run dev   # http://localhost:5173
   ```
   Only run this once at a time. Vite silently picks the next free port
   (5174, 5175, ...) if 5173 is already taken by another `npm run dev`,
   and the backend's CORS only trusts the origins listed in
   `CORS_ALLOWED_ORIGINS` — a stray second dev server is the single most
   common cause of a browser-only "Couldn't load accounts" with a backend
   that's demonstrably up and returning data to `curl`. Comma-separate
   multiple origins in `CORS_ALLOWED_ORIGINS` if you want more than one
   port trusted at once.
4. Sign in through the frontend, then hit
   `POST http://localhost:8000/score/recompute` once with the resulting Supabase
   access token as `Authorization: Bearer ACCESS_TOKEN` to populate
   `health_score`/`alert` rows. Otherwise the Portfolio page will show accounts
   with no score yet.
5. `/score/recompute` only ever persists the *latest* period's score, even
   though it computes one for each period in the account's 3-period trend
   window — so the account-detail chart and accounts-table sparkline will
   show a flat/duplicate-point line until real time passes and new
   `signal_snapshot` periods get ingested. To pull the trend that's
   already latent in the seeded 8-week history into view for a demo, run:
   ```
   cd backend && PYTHONPATH=. python scripts/backfill_health_history.py
   ```
   It's idempotent (skips any date it's already backfilled) and only
   persists scores the real scoring engine already computes — nothing
   fabricated.

`SUPABASE_URL` must be the project's base URL only (e.g.
`https://xxxx.supabase.co`) — not the REST API path. Pasting the REST
endpoint in by mistake produces a `PGRST125` error that looks like the
project is still provisioning but isn't.

`GROQ_MODEL` must be a currently-live model name — Groq deprecates model
IDs over time (`llama-3.3-70b-versatile` no longer exists as of this
writing; `openai/gpt-oss-120b` does). A stale model name fails silently
from the outside: alerts still get a brief, just always the deterministic
fallback text, since `app/services/brief_generation.py` catches the error
and falls back rather than crashing.

## Status

- [x] Repo scaffolding
- [x] Supabase schema — applied to a live project
- [x] Supabase seed data — applied to the live project (15 accounts, 120 signal_snapshot rows)
- [x] FastAPI skeleton
- [x] FastAPI endpoints (`/ingest/csv`, `GET /accounts[/{id}][/signals][/health-history]`,
      `GET /alerts`, `POST/PATCH /alerts/{id}` — all real Supabase reads/writes,
      186/186 tests, merged to `main`, run for real against the live project)
- [x] CSV invoice import — **live-verified**: a real invoice CSV POSTed to the
      production backend correctly matched an account by email, computed
      `invoice_days_late`, and updated the right `signal_snapshot` period
- [x] Gmail/Calendar OAuth ingestion (metadata-only Gmail + read-only Calendar,
      explicit token refresh/scope checks, tested API fetch and snapshot-write path)
- [x] Live Gmail/Calendar account verification — **done**: a real Google OAuth
      connection (exactly the `gmail.metadata` + `calendar.readonly` scopes,
      nothing extra) made a real end-to-end ingest call in ~8.6s. Found and
      fixed a real bug in the process: the Gmail metadata scan had no date
      bound (Gmail blocks the `q` search param under this scope) and would
      have crawled a connected mailbox's *entire* history on every call — now
      bounded to the requested period, with a hard cap as a backstop.
- [x] Scoring engine (`/score/recompute[/{account_id}]` — deterministic composite risk,
      revenue-at-risk, per-signal explainability breakdown, alert dedup; merged to
      `main`, run for real against the live project — 15 accounts scored, 3 alerts
      fired, $349,492.80 total revenue at risk as of 2026-09-13 — this number
      moves whenever scores are recomputed, re-verify before quoting it live)
- [x] Point-of-contact turnover signal (`contact_changed` — a new stakeholder
      taking over an account, derived from `signal_snapshot.primary_contact_email`;
      see HANDOFF.md §5.1). Its migration
      (`supabase/migrations/20260913_contact_turnover_signal.sql`) was committed
      but not actually applied to the live project until it was caught by a
      failing `/score/recompute` call — **now applied and verified**; any other
      already-provisioned project still needs it run manually (see "Running
      locally" above). A visible "new point of contact" callout on the Account
      Detail page is also live (`AccountDetail.tsx`), independent of whether an
      alert has fired.
- [x] Alert revision/optimistic-concurrency migration
      (`supabase/migrations/20260913_alert_brief_persistence.sql`) — same story
      as above: committed but not applied, silently broke every new alert
      insert and brief update (swallowed as a per-account failure, not a
      visible error). **Now applied and verified** — a full `/score/recompute`
      persists all 3 fired alerts with `failed_account_ids: []`.
- [x] Groq brief provider implemented (`retention_radar/briefs.py` + `groq.py`) —
      wired into `POST /score/recompute`, verified against the live Supabase
      project with real LLM-generated briefs. (Gotcha hit later: a stale key
      in production wasn't actually stale — it was a single leading space in
      `GROQ_API_KEY= gsk_...` in `.env`, which produces a `401` with no other
      symptom. Check for that first before assuming a key needs rotating.)
- [x] React (Vite) frontend — redesigned onto a custom flat/Modernist visual
      system (see `frontend/reference/README.md` for the design brief this
      followed); Portfolio, Accounts (new — full sortable/searchable book),
      Account Detail, Alerts, Connections, all wired to the real backend,
      verified in an actual browser session. Per-account risk-score trend
      sparklines added to the accounts table, backed by `/accounts/:id/health-history`.
- [x] Authentication and agency isolation merged to `main`; the live Supabase
      Auth/RLS migration is applied and the production StudioCo admin membership
      is bound
- [x] Authenticated backend deployed on Vercel and verified live: `/health`
      remains public while `/accounts` and `/alerts` reject missing bearer tokens
      with `401`
- [x] Frontend auth build deployed to Render and verified live in a real
      browser session — the "Welcome back / Sign in" gate actually renders,
      no console errors. (Render's auto-deploy on push is configured but has
      proven unreliable more than once — a manual `render deploys create`
      was needed after this merge and the one before it. Don't assume a
      merge alone updated the live frontend; verify the deployed bundle.)
- [x] Render configured with `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and
      `VITE_SUPABASE_ANON_KEY` (never the service-role key)
- [x] Supabase Auth's Site URL set to the production frontend, its callback
      allowed, a real password-recovery email sent and verified end to end:
      callback → session → set password → authenticated `/accounts` request
      → real StudioCo-scoped data
- [x] Backend deployment's `GOOGLE_AGENCY_ID` configured, and live
      Gmail/Calendar ingestion verified against a real connected account
      (see above)
- [ ] Demo run-through rehearsed end to end
