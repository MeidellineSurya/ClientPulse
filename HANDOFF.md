# Handoff: Retention Radar (pitch name: "Rapport")

Behavioral churn early-warning system for retainer-based agencies. If you're
picking this up mid-hackathon, read this top to bottom before touching code —
it's short on purpose.

> **Update:** this build now lives directly in the `ClientPulse` GitHub repo
> root — `frontend/`, `backend/`, `supabase/` are top-level folders, not
> nested under a `/rapport` subfolder. The frontend stack also changed from
> Next.js to **Vite + React + React Router** (still TypeScript, Tailwind,
> shadcn/ui, Recharts). Pitch/product naming decisions in §7 are unaffected —
> flagging this here since it touches the repo layout in §4 and stack in §3.

---

## 1. The pitch, in one breath

Marketing/creative agencies lose clients with no warning because every AI
churn-prediction tool (Gainsight, ChurnZero, Pendo) requires product usage
data agencies don't have — their "product" is a relationship, not software.
Clients actually leave over poor communication and weak guidance (not price),
and that shows up as behavior — slower replies, more cancelled meetings,
later invoice payments — weeks before anyone says a word. Rapport watches
that drift using data agencies already have (Gmail, Calendar, invoices) and
flags accounts before renewal, not after.

**Money case:** losing one $10K/month client costs an agency ~$140K
(lost revenue + sunk onboarding + replacement cost). Saving one account a
year pays for the tool many times over at a $150-300/month price point.

Full detail: see `PRD-retention-radar.md` in this same output — problem
statement, scoring formula, data model, and screen-by-screen spec live there.
This file is the "what do I need to know to keep building" doc, not the pitch
doc.

## 2. Current status

> Update this checklist as you go — it's the fastest way for anyone
> rejoining mid-build to know where things actually stand.

- [x] Repo scaffolding (folders, README, .env.example)
- [x] Supabase schema.sql written (not yet applied to a live Supabase project)
- [x] Supabase seed data (StudioCo + 15 mock accounts, 8-week history, 3 trending
      worse — `backend/scripts/generate_seed.py` -> `supabase/seed.sql`; not yet
      applied to a live Supabase project)
- [x] FastAPI skeleton running (`/health` responds)
- [ ] FastAPI endpoints stubbed (`/accounts`, `/alerts`, `/ingest/csv`) — `/ingest/csv`
      done and fully wired to Supabase (parses CSV, matches account/period, writes
      `invoice_days_late`, tested); `/accounts` and `/alerts` not started (owned by
      other workstreams, not ingestion)
- [ ] Gmail/Calendar pull (stretch) — `/ingest/gmail-calendar/{account_id}` scaffolded
      end-to-end (metadata-only Gmail scope, Calendar events, DB upsert) and unit-tested
      on the pure signal computation + repo logic, but **not exercised against a live
      Google account** — no OAuth credentials available in this environment. Needs real
      `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`GOOGLE_REFRESH_TOKEN` to actually run.
- [ ] Groq client stub in place
- [ ] Frontend (Vite + React) skeleton running
- [ ] Portfolio page (hardcoded data)
- [ ] Account detail page (hardcoded data + charts)
- [ ] Alerts inbox page
- [ ] Settings/connections page
- [x] **Scoring engine implemented (the core feature — see §5)** — `baseline_engine.py`
      (rolling avg/stddev per signal) + `scoring_engine.py` (drift, weighted composite
      risk, worsening-trend-gated alert decision, exactly the §5 formula) +
      `scoring_repo.py` + `POST /score/recompute[/{account_id}]`, on branch
      `feat/baseline-scoring-engine`. 51/51 tests passing; validated against the real
      seed data — flags exactly the 3 seeded worsening accounts (scores 97.6–100),
      clean gap to every stable account (next-highest 38.4). **Not yet run against a
      live Supabase project** (same caveat as ingestion — no live project yet).
      `RISK_ALERT_THRESHOLD=60`, severity buckets (70/85/95), and `Z_CAP=3.0` are
      placeholders empirically tuned against seed data, not values specified in this
      doc — revisit once real accounts flow through ingestion.
- [ ] LLM brief generation wired with real prompt (not stub)
- [ ] Frontend connected to backend (no more hardcoded arrays)
- [ ] Live Gmail/Calendar pull (stretch goal, cut first if behind)
- [ ] Demo run-through rehearsed end to end

## 3. Stack (reused deliberately, nothing new to learn under time pressure)

| Layer | Choice |
|---|---|
| Frontend | React (Vite) + TypeScript + React Router + Tailwind + shadcn/ui + Recharts |
| Backend | FastAPI (Python) |
| Database | Supabase (Postgres) |
| LLM | Groq — `llama-3.3-70b-versatile` |
| Data sources | Gmail + Google Calendar (live-capable in this environment) + CSV upload for invoices |
| Deploy | Vercel (frontend) / Railway (backend) |

## 4. Repo layout

```
ClientPulse/          (repo root)
  /frontend          React (Vite) app
  /backend           FastAPI app
  /supabase          schema.sql, seed.sql
  README.md
  .env.example
```

## 5. The one piece that must not get rushed: the scoring engine

Everything else in this project is normal CRUD/dashboard work. The scoring
engine is the entire defensibility argument for the pitch — a judge asking
"how is this calculated" needs a real, reproducible answer, not "the AI
figures it out."

**Rule: the LLM never generates the risk score.** It only writes the
plain-language brief *after* the deterministic score already exists.

```
drift_score(signal) = (current_value - baseline_avg) / baseline_stddev
                        [normalized/clipped to 0–1]

composite_risk =
    0.35 × drift(response_time)          # top churn cause: poor communication
  + 0.30 × drift(meeting_cancellations)
  + 0.20 × drift(payment_lag)
  + 0.15 × drift(meeting_frequency_decline)
```

An alert only fires when `composite_risk` crosses threshold **and** the
trend over the last 3 periods is worsening — a single bad week should not
trigger a flag. If you're the person owning this piece and you're behind
schedule, cut chart polish or the live API integrations before you cut this
trend-requirement check — it's what separates the product from a vanity
dashboard.

## 6. Data model reference

See `supabase/schema.sql` for the authoritative version. Six tables:
`agency`, `account`, `signal_snapshot`, `baseline`, `health_score`, `alert`.
Full field list is in the PRD (§6) if the schema file isn't in front of you.

## 7. Decisions already made (don't relitigate mid-build)

- **No client-facing automation.** The agent only alerts internal staff —
  it never contacts a client directly. This was a deliberate choice after
  ruling out other ideas with liability/trust problems; keep it that way.
- **CSV upload stands in for Xero**, not a live accounting API integration —
  out of scope for the hackathon window.
- **Every client's "normal" is its own baseline**, not a global benchmark —
  this is why the drift formula divides by that account's own rolling
  stddev, not a portfolio-wide average.
- **Name:** working repo/build name is "Retention Radar"; the pitch-facing
  name is "Rapport." Use whichever is already in the codebase — don't
  rename mid-build.

## 8. Known limitations (state these in the pitch, don't hide them)

- Financial data is CSV-based, not a live integration
- Baselines need real historical data to mean anything in production; the
  demo relies on seeded 8-week history to simulate that
- No client consent/data-scoping flow yet for reading email — only
  metadata (response time), not email content, is used, and that should be
  said explicitly if asked

## 9. Demo script (rehearse this, don't wing it)

1. Portfolio view → 15 seeded accounts, sorted by risk, at-risk revenue
   total shown at top
2. Click into a flagged account → trend charts + plain-language AI brief
3. Alerts inbox → "this is what an account manager checks every morning"
4. Close on the money: one saved $10K/month account ≈ $140K avoided,
   against a $150-300/month price tag

## 10. If you get stuck / need to cut scope

Cut in this order, stopping as soon as the demo is coherent again:
live Gmail/Calendar API → chart polish/animation → separate alerts-inbox
page (fold into portfolio view) → CSV upload UI (hardcode one seeded file).
**Never cut:** the deterministic scoring formula or the worsening-trend
check — that's the whole pitch.
