# ClientPulse

Behavioral churn early-warning tool for retainer-based agencies. Surfaces accounts
that are quietly drifting toward churn (slower replies, more cancellations, late
invoices) before the client says anything.

**🌐 Live:** [clientpulse-frontend.onrender.com](https://clientpulse-frontend.onrender.com)
(backend: [backend-ruddy-rho-34.vercel.app](https://backend-ruddy-rho-34.vercel.app))

> 🚧 Hackathon build. This repo is being scaffolded incrementally — see commit
> history for progress. Backend + frontend are live and verified end-to-end
> against a real Supabase project, including real Groq-generated AI briefs on
> alerts. Production Gmail/Calendar OAuth ingestion is implemented, but
> live-account verification still needs project-specific Google credentials.
> `app/services/scoring_engine.py` is confirmed as the sole alert-decision
> engine — see HANDOFF.md.
>
> Pitch, scoring formula, product decisions, and demo script: see
> [HANDOFF.md](./HANDOFF.md).

## Stack

- **Frontend:** React (Vite), TypeScript, React Router, Tailwind CSS, shadcn/ui, Recharts
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

1. **Database:** create a Supabase project, then run `supabase/schema.sql`
   followed by `supabase/seed.sql` in its SQL Editor. Create a user under
   Supabase Authentication, then insert that user's UUID and the seeded agency
   UUID into `agency_member`. Each user belongs to exactly one agency.
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
4. Sign in through the frontend. Protected API calls require the resulting
   Supabase access token as `Authorization: Bearer <token>`. Run
   `POST http://localhost:8000/score/recompute` with that header once to
   populate `health_score`/`alert` rows before loading the portfolio.

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
      146/146 tests, merged to `main`, run for real against the live project)
- [x] Gmail/Calendar OAuth ingestion (metadata-only Gmail + read-only Calendar,
      explicit token refresh/scope checks, tested API fetch and snapshot-write path)
- [ ] Live Gmail/Calendar account verification (no Google credentials available yet)
- [x] Scoring engine (`/score/recompute[/{account_id}]` — deterministic composite risk,
      revenue-at-risk, per-signal explainability breakdown, alert dedup; merged to
      `main`, run for real against the live project — 15 accounts scored, 3 alerts
      fired, $418,369.20 total revenue at risk)
- [x] Groq brief provider implemented (`retention_radar/briefs.py` + `groq.py`) —
      wired into `POST /score/recompute`, verified against the live Supabase
      project with real LLM-generated briefs
- [x] React (Vite) frontend — Portfolio, Account Detail, Alerts, Settings, all
      wired to the real backend, verified in an actual browser session
- [x] Deployment — frontend live on Render, backend live on Vercel (Python
      ASGI serverless), both verified end-to-end in a real browser session
      against the actual production URLs
- [x] Supabase Auth bearer validation and backend-enforced agency isolation,
      including tenant-scoped accounts, signals, alerts, ingestion, and scoring
- [ ] Deploy auth migration, create the production agency membership, and add
      the frontend's public Supabase Auth environment values
- [ ] Demo run-through rehearsed end to end
