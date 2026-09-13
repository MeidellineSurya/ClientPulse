# ClientPulse frontend

React + Vite + TypeScript + React Router + Recharts. Custom flat "Modernist"
design system (zero border-radius, ink-on-light-ground, single red accent,
Archivo font) — no component library (shadcn/radix were removed during the
redesign).

## Run

```
cp .env.example .env.local   # VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev                  # http://localhost:5173
```

Run only one dev server at a time. Vite silently falls back to the next
free port (5174, 5175, ...) if 5173 is taken, and the backend's CORS only
trusts the origins listed in its `CORS_ALLOWED_ORIGINS` — a stray second
`npm run dev` is the most common cause of a browser-only "Couldn't load
accounts" while the backend is demonstrably up.

## Data flow

`src/lib/api.ts` + `src/types/api.ts` are the only data boundary — every
page fetches through `api.*`, and the types mirror `backend/app/schemas.py`
exactly. There is no mock mode; this always talks to the real FastAPI
backend at `VITE_API_BASE_URL`. See the root `README.md` for how to get
the backend running.

`composite_score` is a **risk** score (0-100, higher = worse) — see
`backend/app/services/scoring_engine.py`. The UI labels it "Risk", not
"Health", deliberately: inverting it for display would mean showing a
number the backend never actually computed.

## Layout

```
src/lib/api.ts          fetch wrapper — the only data boundary
src/types/api.ts        types mirroring backend/app/schemas.py
src/lib/format.ts       formatCurrency, riskTier, severityStyles, signalStatus, etc.
src/lib/utils.ts        cn(), RISK_STYLES / HEX colour maps, nearestByDate
src/lib/useCachedByIds.ts      shared cross-component fetch cache + concurrency throttle
src/lib/useHealthHistories.ts  per-account health-history, built on useCachedByIds
src/lib/useSignalHistories.ts  per-account raw signal history, built on useCachedByIds
src/components/         AccountTable, AlertCard, TrendSparkline, layout/AppLayout, ui/*
src/pages/              Portfolio, Accounts, AccountDetail, Alerts, Connections
```

## Design reference

`reference/` holds the original design mock this UI was built from
(`ClientPulse-design-reference.html`, standalone — open directly in a
browser) plus its mock scoring engine and seed data (`src/lib/scoring.js`,
`src/data/`), kept verbatim but **not imported anywhere** — see
`reference/README.md` for why (it computes a different, incompatible
scoring model) and for the list of design-brief gaps deliberately deferred
rather than faked with client-side data (renewal date, score audit panel,
signal baseline bands).
