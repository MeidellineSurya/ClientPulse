# ClientPulse

Behavioral churn early-warning tool for retainer-based agencies. Surfaces accounts
that are quietly drifting toward churn (slower replies, more cancellations, late
invoices) before the client says anything.

> 🚧 Hackathon build. This repo is being scaffolded incrementally — see commit
> history for progress. Production Gmail/Calendar OAuth ingestion is implemented,
> but live-account verification still needs project-specific Google and Supabase
> credentials. Scoring logic is implemented but not yet run against live Supabase.
>
> Pitch, scoring formula, product decisions, and demo script: see
> [HANDOFF.md](./HANDOFF.md).

## Stack

- **Frontend:** React (Vite), TypeScript, React Router, Tailwind CSS, shadcn/ui, Recharts
- **Backend:** FastAPI (Python 3.11+), Pydantic
- **Database:** Supabase (Postgres)
- **LLM:** Groq (`llama-3.3-70b-versatile`)
- **Deploy:** Vercel (frontend), Railway (backend)

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

Full run instructions land once both apps are scaffolded (see steps in commit
history). Each app also has its own `.env.example` to copy from.

## Status

- [x] Repo scaffolding
- [x] Supabase schema
- [x] Supabase seed data (generated, not yet applied to a live project)
- [x] FastAPI skeleton
- [x] FastAPI endpoints (`/ingest/csv`, `GET /accounts[/{id}][/signals]`, `GET /alerts`,
      `POST /alerts/{id}/status` — all real Supabase reads/writes, 98/98 tests;
      `feat/accounts-alerts-endpoints` — not yet run against a live Supabase project)
- [x] Gmail/Calendar OAuth ingestion (metadata-only Gmail + read-only Calendar,
      explicit token refresh/scope checks, tested API fetch and snapshot-write path)
- [ ] Live Gmail/Calendar account verification (no project credentials available yet)
- [x] Scoring engine (`/score/recompute[/{account_id}]` — deterministic composite risk,
      revenue-at-risk, per-signal explainability breakdown, alert dedup; 74/74 tests;
      `feat/baseline-scoring-engine` — not yet run against a live Supabase project)
- [x] Groq client stub
- [ ] React (Vite) skeleton
- [ ] Frontend pages
