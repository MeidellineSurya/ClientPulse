# ClientPulse

Behavioral churn early-warning tool for retainer-based agencies. Surfaces accounts
that are quietly drifting toward churn (slower replies, more cancellations, late
invoices) before the client says anything.

> 🚧 Hackathon build. This repo is being scaffolded incrementally — see commit
> history for progress. Scoring logic, real Gmail/Calendar integration, and auth
> are intentionally not implemented yet.
>
> Pitch, scoring formula, product decisions, and demo script: see
> [HANDOFF.md](./HANDOFF.md).

## Stack

- **Frontend:** React (Vite), TypeScript, React Router, Tailwind CSS, shadcn/ui, Recharts
- **Backend:** FastAPI (Python 3.11+), Pydantic
- **Database:** Supabase (Postgres)
- **LLM:** Groq (`openai/gpt-oss-120b`)
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
- [ ] Supabase seed data
- [ ] FastAPI skeleton
- [ ] FastAPI endpoints
- [x] Groq brief provider and deterministic alert module
- [ ] React (Vite) skeleton
- [ ] Frontend pages
