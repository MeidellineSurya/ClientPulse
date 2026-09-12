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
- [x] Supabase schema.sql — **applied to a live Supabase project** (all 6 tables + indexes)
- [x] Supabase seed data — **applied to the live project**: StudioCo + 15 accounts,
      8-week history each (120 `signal_snapshot` rows), 3 trending worse. Verified
      via direct query against the real database.
- [x] FastAPI skeleton running (`/health` responds)
- [x] FastAPI endpoints (`/accounts`, `/alerts`, `/ingest/csv`) — now on `main`.
      `/ingest/csv` fully wired to Supabase. `GET /accounts`, `GET
      /accounts/{id}[/signals][/health-history]`, `GET /alerts` (with `?status=`
      filter), `POST/PATCH /alerts/{id}` — real Supabase reads, account list joins
      latest `health_score`, alerts join account name, status transitions validated
      with optimistic concurrency control (no reopening resolved alerts, no moving
      backwards). 146/146 tests passing. **Run for real against the live Supabase
      project** — verified end-to-end in an actual browser session.
- [x] Gmail/Calendar OAuth ingestion — `/ingest/gmail-calendar/{account_id}` now
      uses the production metadata-only Gmail and read-only Calendar APIs, eagerly
      refreshes and scope-checks OAuth credentials, filters Gmail headers locally
      because `gmail.metadata` forbids server-side `q`, maps Google failures cleanly,
      validates periods/UUIDs, and tests the complete fetch → compute → Supabase
      snapshot-write path without reading message bodies. Live-account verification
      still needs project-specific Google credentials (Supabase side is now live).
- [x] Groq brief provider implemented (`openai/gpt-oss-120b`, validated JSON +
      deterministic fallback) — **now wired into `POST /score/recompute`**
      (`app/groq_client.py` + `app/services/brief_generation.py`). Fixed 3 real
      bugs found while getting a live call to actually succeed: `retention_radar
      /groq.py`'s bare `urllib` had no CA cert bundle (fails on any python.org
      macOS install), Groq's Cloudflare front blocks Python's default
      User-Agent as a bot signature, and the test suite would otherwise make
      real network calls to Groq on every run (fixed with an autouse
      `tests/conftest.py` fixture). Verified against the live Supabase project
      with a real `GROQ_API_KEY` — alerts now carry genuine LLM-generated
      briefs, confirmed causal-claim-free and auto-contact-free by inspecting
      the actual text.
- [x] Deterministic alert trigger implemented — see ⚠️ below, **two unreconciled
      implementations exist**.
- [x] Frontend (Vite + React) skeleton running — on `feat/frontend-app`, merged with
      the latest `main`. TypeScript + Tailwind v4 + shadcn/ui + React Router + Recharts.
- [x] Portfolio page — real data, sortable table, color-coded health scores, trend
      arrows, total-at-risk-revenue summary bar
- [x] Account detail page — real Recharts trend charts per signal, composite-score
      history chart (via the new `/health-history` endpoint), revenue at risk
- [x] Alerts inbox page — real alerts, status-update button wired to the live endpoint
- [x] Settings/connections page — UI only, matches spec ("not wired up yet")
- [x] **Scoring engine implemented (the core feature — see §5)** — `baseline_engine.py`
      (rolling avg/stddev per signal) + `scoring_engine.py` (drift, weighted composite
      risk, worsening-trend-gated alert decision, exactly the §5 formula) +
      `scoring_repo.py` + `POST /score/recompute[/{account_id}]`, now on `main`.
      Validated against the real seed data — flags exactly the 3 seeded worsening
      accounts (scores 97.6–100), clean gap to every stable account (next-highest
      38.4). **Now run for real against the live Supabase project**, not just seed
      data in isolation. `RISK_ALERT_THRESHOLD=60`, severity buckets (70/85/95), and
      `Z_CAP=3.0` are placeholders empirically tuned against seed data, not values
      specified in this doc.
      Also included: **`revenue_at_risk`** per account (feeds the Portfolio page's
      summary bar with a real number — $418,369.20 across the 3 live-flagged
      accounts) and **`total_revenue_at_risk`** on the batch endpoint;
      **`signal_contributions`** — a %-breakdown of which signals drove each score;
      alert de-duplication so repeated recompute calls escalate/refresh an existing
      open alert instead of spamming duplicates.
- [x] LLM brief generation implemented with real evidence-bound prompt (`retention_radar/briefs.py`)
      and **now fully wired end-to-end** — see the Groq brief provider item above
- [x] Frontend connected to backend — real fetches throughout, no hardcoded arrays,
      verified in an actual headless-browser session against the live project
- [ ] Live Gmail/Calendar pull (stretch goal, cut first if behind — no Google
      credentials available yet, Supabase side is otherwise ready)
- [ ] Demo run-through rehearsed end to end

> ⚠️ **Open item: two unreconciled implementations of the deterministic alert
> *decision*.** `app/services/scoring_engine.py` (live, wired to `POST
> /score/recompute`, verified end-to-end against the real Supabase project) and
> `backend/retention_radar/alerts.py`'s `evaluate_alert` (same core idea —
> threshold crossing + 3-period worsening trend — built independently, different
> scale/severity buckets/dedup strategy, **still not imported anywhere in
> `app/`**) both exist right now. The team needs to decide whether to keep only
> one, or under what circumstances (if any) the second would ever run. Flagging
> here rather than silently picking one — this is exactly the kind of decision
> HANDOFF §5 says shouldn't get rushed.
>
> **Resolved:** the brief-*generation* half of this — `retention_radar
> /briefs.py` + `groq.py` is now the one and only brief generator, wired into
> `scoring_engine.py`'s pipeline (see the Groq brief provider item in §2). No
> third implementation was built; the decision engine stayed singular.

## 3. Stack (reused deliberately, nothing new to learn under time pressure)

| Layer | Choice |
|---|---|
| Frontend | React (Vite) + TypeScript + React Router + Tailwind + shadcn/ui + Recharts |
| Backend | FastAPI (Python) |
| Database | Supabase (Postgres) |
| LLM | Groq — `openai/gpt-oss-120b` |
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

1. Portfolio view → 15 real accounts (live Supabase, not a mock), sorted by
   risk, at-risk revenue total shown at top — $418,369.20 across the 3
   flagged accounts, a real computed number
2. Click into a flagged account → real Recharts trend charts per signal +
   composite-score-over-time chart, plus a real Groq-generated AI brief card
   citing the actual `signal_contributions` — "here's exactly why this
   account is flagged," in the account manager's own words, if a judge
   pushes on it
3. Alerts inbox → real alerts, status-update button works live —
   "this is what an account manager checks every morning"
4. Close on the money: one saved $10K/month account ≈ $140K avoided,
   against a $150-300/month price tag

## 10. If you get stuck / need to cut scope

Cut in this order, stopping as soon as the demo is coherent again:
live Gmail/Calendar API → chart polish/animation → separate alerts-inbox
page (fold into portfolio view) → CSV upload UI (hardcode one seeded file).
**Never cut:** the deterministic scoring formula or the worsening-trend
check — that's the whole pitch.
