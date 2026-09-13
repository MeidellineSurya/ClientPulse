# Handoff: Retention Radar (pitch name: "Rapport")

Behavioral churn early-warning system for retainer-based agencies. If you're
picking this up mid-hackathon, read this top to bottom before touching code —
it's short on purpose.

> **Update:** this build now lives directly in the `ClientPulse` GitHub repo
> root — `frontend/`, `backend/`, `supabase/` are top-level folders, not
> nested under a `/rapport` subfolder. The frontend stack also changed from
> Next.js to **Vite + React + React Router** (still TypeScript, Tailwind,
> Recharts). Pitch/product naming decisions in §7 are unaffected —
> flagging this here since it touches the repo layout in §4 and stack in §3.
>
> **Second update:** the frontend was later redesigned onto a custom flat
> "Modernist" visual system — shadcn/ui and radix-ui are gone, replaced by
> hand-rolled components (see `frontend/reference/README.md`). Same data
> boundary (`lib/api.ts`, `types/api.ts`) and business logic throughout;
> only the UI layer changed.

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
- [x] Gmail/Calendar OAuth ingestion — **live-verified against a real Google
      account** (2026-09-13). `/ingest/gmail-calendar/{account_id}` uses the
      production metadata-only Gmail and read-only Calendar APIs, eagerly
      refreshes and scope-checks OAuth credentials (confirmed granting exactly
      `gmail.metadata` + `calendar.readonly`, nothing extra), maps Google
      failures cleanly, validates periods/UUIDs. A real end-to-end call against
      a live-connected mailbox completed in ~8.6s and wrote a real
      `signal_snapshot` row. **Found and fixed a real bug during that live
      test:** `gmail_signals.fetch_message_metadata` had no date bound at all
      (Gmail blocks the `q` search param under `gmail.metadata` scope) — it
      was paging through and fetching metadata for a connected mailbox's
      *entire* history on every call, regardless of the requested period. Now
      relies on Gmail's newest-first list ordering to stop as soon as it walks
      past the period, plus a hard 500-message cap as a backstop either way —
      see `gmail_signals.py` and its tests. **Real credentials are configured
      in both `backend/.env` and the Vercel backend's production env**, bound
      to a specific `GOOGLE_AGENCY_ID` (StudioCo).
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
      the actual text. **A 4th real bug, found later (2026-09-13):** the key
      briefly went stale in production after a rotation — turned out to be a
      single leading space in `backend/.env` (`GROQ_API_KEY= gsk_...` instead
      of `GROQ_API_KEY=gsk_...`), which produces a 401 with no other symptom.
      Worth checking first if a Groq call ever silently falls back after a
      key rotation.
- [x] Deterministic alert trigger implemented — `scoring_engine.py` confirmed as
      the sole decision engine, see ✅ below.
- [x] Frontend (Vite + React) skeleton running — on `feat/frontend-app`, merged with
      the latest `main`. TypeScript + Tailwind v4 + React Router + Recharts.
      Later redesigned onto a custom flat/"Modernist" visual system (zero
      border-radius, ink-on-light-ground, single red accent) — shadcn/ui and
      radix-ui were dropped entirely in favor of hand-rolled components; see
      `frontend/reference/README.md` for the design brief and the known gaps
      it left (renewal date, score audit panel, baseline bands — deferred,
      not forgotten).
- [x] Portfolio page — real data, sortable table, color-coded risk scores, trend
      arrows/sparklines, total-at-risk-revenue summary bar
- [x] Accounts page (new) — full sortable/searchable/filterable book, split out
      from Portfolio's shortlist view
- [x] Account detail page — real Recharts trend charts per signal, composite-score
      history chart (via the new `/health-history` endpoint), revenue at risk
- [x] Alerts inbox page — real alerts, status-update button wired to the live endpoint
- [x] Connections page (renamed from Settings) — UI only, matches spec ("not wired up yet")
- [x] Per-account risk-score trend sparklines on the accounts table — one
      `/accounts/:id/health-history` fetch per visible row, cached per mount.
      Building this exposed that `/score/recompute` only ever persists the
      *last* of the 3 scores it computes per call (see §5's trend-window
      note) — every prior call against unchanged seed data had been
      inserting duplicate points, not new ones. `backend/scripts/
      backfill_health_history.py` is a one-time, idempotent script that
      persists the other 2 already-computed-but-discarded points per
      account, so the seed data's baked-in worsening trend (3 accounts,
      see `WORSENING_INDEXES` in `generate_seed.py`) is actually visible.
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
      summary bar with a real number — $349,492.80 across the 3 live-flagged
      accounts as of 2026-09-13, after the contact-turnover reweight and the
      Anchor & Ives contact-history backfill; this number moves whenever the
      signals/weights change, don't treat it as fixed) and
      **`total_revenue_at_risk`** on the batch endpoint;
      **`signal_contributions`** — a %-breakdown of which signals drove each score;
      alert de-duplication so repeated recompute calls escalate/refresh an existing
      open alert instead of spamming duplicates.
- [x] LLM brief generation implemented with real evidence-bound prompt (`retention_radar/briefs.py`)
      and **now fully wired end-to-end** — see the Groq brief provider item above
- [x] Frontend connected to backend — real fetches throughout, no hardcoded arrays,
      verified in an actual headless-browser session against the live project
- [x] CSV invoice import — **live-verified** (2026-09-13): a real CSV POSTed to
      the production backend correctly matched an account by email, computed
      `invoice_days_late`, and updated the right `signal_snapshot` period
      (confirmed by re-reading the row afterward).
- [x] Contact-turnover signal (`contact_changed`) — a new point of contact on
      an account, live in the composite score since PR #14, with a visible
      "New point of contact" callout on Account Detail since PR #18 (was §13,
      now resolved — see the note at the end of this doc).
- [x] Live Gmail/Calendar pull — see the checklist item above; no longer a
      stretch goal, done and verified against a real connected account.
- [ ] Demo run-through rehearsed end to end

> ✅ **Resolved: the two unreconciled alert-decision implementations.**
> `app/services/scoring_engine.py` is the one and only alert decision engine —
> live, wired to `POST /score/recompute`, validated against the real seed data
> (exact 3/15 separation), verified end-to-end against the live Supabase
> project. `backend/retention_radar/alerts.py`'s `evaluate_alert` (built
> independently, same core idea, never run against real data, stricter
> monotonic trend requirement, caller-tracked dedup that doesn't fit a
> "recompute anytime" call pattern) is **not** wired in and never will be —
> its module docstring now says so explicitly, kept only for reference rather
> than deleted outright. Same resolution as brief generation below: no third
> implementation, the decision stayed singular.
>
> **Also resolved: brief generation.** `retention_radar/briefs.py` + `groq.py`
> is the one and only brief generator, wired into `scoring_engine.py`'s
> pipeline (see the Groq brief provider item in §2). No third implementation
> was built.

## 3. Stack (reused deliberately, nothing new to learn under time pressure)

| Layer | Choice |
|---|---|
| Frontend | React (Vite) + TypeScript + React Router + Tailwind + Recharts — custom flat/Modernist design system, not shadcn/ui (dropped during the frontend redesign; see `frontend/reference/README.md`) |
| Backend | FastAPI (Python) |
| Database | Supabase (Postgres) |
| LLM | Groq — `openai/gpt-oss-120b` |
| Data sources | Gmail + Google Calendar (live-capable in this environment) + CSV upload for invoices |
| Deploy | Render (frontend, static site) / Vercel (backend, Python ASGI serverless) — see §11 |

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
    0.30 × drift(response_time)          # top churn cause: poor communication
  + 0.25 × drift(meeting_cancellations)
  + 0.20 × drift(contact_turnover)       # new point of contact on the account
  + 0.15 × drift(payment_lag)
  + 0.10 × drift(meeting_frequency_decline)
```

`contact_turnover` was added after the original four (§5.1) — a new point
of contact taking over an account is one of the strongest churn predictors
in agency relationships, and unlike the other four it's a discrete event
(did the contact email change this period?) rather than a continuously
drifting quantity. It's derived, not a raw `signal_snapshot` column — see
`app/services/baseline_engine.py::derive_contact_changed` — and the other
four weights were reweighted down proportionally to make room for it
rather than letting the total exceed 1.0.

### 5.1 Signal reference

| Signal | Weight | Source | Direction |
|---|---|---|---|
| `avg_response_time_hours` | 0.30 | Gmail metadata | higher = worse |
| `meetings_cancelled` | 0.25 | Calendar | higher = worse |
| `contact_changed` | 0.20 | derived from `signal_snapshot.primary_contact_email` | any change = worse |
| `invoice_days_late` | 0.15 | CSV invoice ingest | higher = worse |
| `meetings_scheduled` | 0.10 | Calendar | *lower* = worse (frequency decline) |

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

`signal_snapshot.primary_contact_email` (added in
`supabase/migrations/20260913_contact_turnover_signal.sql`) stamps the
account's *current* contact onto each period as it's ingested — it's how
`contact_changed` (§5.1) detects a stakeholder change between periods.
**Any already-provisioned Supabase project needs that migration applied**
before deploying a backend built off this branch or later, the same as the
alert-brief-persistence migration before it.

Both migrations were committed to this repo well before either was
actually run against the live project — and neither failure mode looked
like a missing migration from the outside. Missing
`primary_contact_email` 500'd every call to `fetch_signal_history`
(`/score/recompute` and the new backfill script both use it), and missing
`alert.revision` silently failed every new alert insert and brief update,
swallowed by `/score/recompute`'s per-account error isolation into
`failed_account_ids` rather than surfaced as an error. Both are now
applied and verified against the live project (confirmed via a real
`/score/recompute` returning `failed_account_ids: []` with alerts
actually persisted). **Lesson for next time:** a migration file existing
in the repo is not evidence it's been run — verify by querying the
column/constraint directly, or by exercising the code path that depends
on it, not by checking git log.

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
   risk, at-risk revenue total shown at top — $349,492.80 across the 3
   flagged accounts as of 2026-09-13, a real computed number (re-verify
   this figure before a live demo — it moves whenever scores are recomputed)
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

## 11. Deployment (not the original Vercel/Railway plan — both required a card)

**Live now:**
- Frontend: [clientpulse-frontend.onrender.com](https://clientpulse-frontend.onrender.com)
  — Render static site, deployed from `frontend/` via `render services create --type static_site`
- Backend: [backend-ruddy-rho-34.vercel.app](https://backend-ruddy-rho-34.vercel.app)
  — Vercel Python ASGI serverless function, deployed from `backend/` via `vercel deploy --prod`

**Why not the original plan:** Railway's trial was expired and required a
paid plan to create a new project; Render's compute tier (a real web
service) required a card on file for fraud-prevention verification even to
use the free tier. Neither is a Render/Railway-specific problem — this is
now standard across most PaaS providers. Render's **static-site** tier and
Vercel's **Python serverless** runtime both required no card at all, so the
split flipped: frontend → Render, backend → Vercel (the reverse of the
original plan, which had frontend → Vercel, backend → Railway).

**How the backend is structured for this:** `backend/api/index.py` is a
one-line Vercel entrypoint that re-exports `app` from `app/main.py` — the
actual FastAPI app is unaware of Vercel and still runs locally exactly the
same way (`uvicorn app.main:app`). `backend/vercel.json` is intentionally
empty (`{}`): Vercel auto-detects the FastAPI framework and handles routing
itself; an earlier attempt at an explicit rewrite rule broke routing by
stripping the original request path before it reached the app.

**Real gotchas hit getting here** (all now fixed, see git history):
- Passing multiple secrets as `--env-var` flags in one shell command was
  blocked by an auto-mode safety classifier (credential leakage risk via
  process-argument visibility) — fixed by setting secrets one at a time via
  `vercel env add`, piped through stdin from `backend/.env` rather than
  passed as literal command arguments.
- Render's CLI can't update env vars on an *existing* service (`services
  update` has no `--env-var` flag) — updating `VITE_API_BASE_URL` after the
  backend's real URL was known required deleting and recreating the static
  site, not editing it in place. Fine here since it's a stateless build.
- Env vars only apply on the *next* deploy — after setting Vercel's env
  vars, a fresh `vercel deploy --prod` was needed before `/accounts` could
  reach Supabase.

**Current redeploy behavior (last confirmed 2026-09-13, after several more
merges to `main`):**
- **Backend (Vercel):** Git integration is confirmed reliable — every merge to
  `main` since (`b242f0c`, PR #18, PR #19) triggered an automatic Production
  deployment within seconds, no manual step needed. `/health` returns `200`,
  unauthenticated `/accounts`/`/alerts` return `401`.
- **Frontend (Render):** auto-deploy (`autoDeploy: yes`, `autoDeployTrigger:
  commit`) is configured correctly but **still does not reliably fire** — this
  was re-confirmed twice more (PR #17 and PR #18 both required a manual
  `render deploys create` before the live bundle actually updated; deploy
  history showed no new deploy had been triggered by either merge on its own).
  **Don't assume a merge to `main` updated the live frontend** — always verify
  by checking the deployed bundle for expected new-code markers (or just
  trigger a manual deploy after every merge that touches `frontend/`) until
  someone actually debugs the GitHub webhook on Render's side.

## 12. Authentication deployment handoff

**Completed:**
- Bearer authentication and server-resolved agency isolation are merged to
  `main` at `b242f0c`.
- The alert-persistence and auth/RLS migrations are applied to live Supabase.
- `public.agency_member` contains the production StudioCo admin binding.
- Live PostgREST verification exercised alert revisions `0 → 1 → 2`, rejected a
  stale compare-and-swap update, rejected a duplicate active alert, and cleaned
  up all temporary verification rows.
- The backend production deployment is live and denies unauthenticated protected
  routes.
- The frontend includes restored-session token ordering and invite/recovery
  password setup; the final local gates were 182 backend tests, 8 frontend tests,
  frontend production build, and frontend lint.

**All 6 steps below are done and verified (2026-09-13) — kept for the record,
not because anything is still outstanding:**
1. ~~Set `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` on
   the Render frontend.~~ Done.
2. ~~Trigger a Render deployment and prove the live bundle contains the
   auth/password-setup flow.~~ Done — confirmed via a real headless-browser
   load showing the actual "Welcome back / Sign in" gate.
3. ~~Set Supabase Auth's Site URL to the real Render frontend and add its
   redirect wildcard to the allowlist.~~ Done.
4. ~~Get a properly-scoped Supabase token, or do step 3 by hand.~~ Done by
   hand in the dashboard.
5. ~~Send a fresh password-recovery email and verify the full loop.~~ Done —
   real recovery email → real click-through → set password → authenticated
   `/accounts` request returned real StudioCo-scoped data (confirmed via
   DevTools Network tab, 200 with real account names, not empty/401).
6. ~~Configure `GOOGLE_AGENCY_ID` in the backend deployment.~~ Done — set on
   Vercel production, redeployed, verified.

One real gotcha hit along the way, worth keeping: the first recovery email
click failed with `otp_expired` even though it was clicked almost
immediately — the likely cause is an email client/security scanner
auto-visiting the link before the human did, consuming the one-time token.
Resending and clicking immediately worked. If this happens again, check
Supabase Auth Logs for two verify attempts close together.

No customer UUIDs, email addresses, tokens, passwords, project references, API
keys, or OAuth credentials belong in this document or the repository.

## 13. Contact turnover on Account Detail — resolved

> ✅ **Resolved (PR #18, 2026-09-13).** Implemented exactly as specified
> below: `GET /accounts/{id}` now returns `contact_changed_at` /
> `previous_contact_email` (derived server-side via the same
> `baseline_engine.derive_contact_changed` the scoring engine uses, so it
> can never disagree with what actually drove the score), and
> `AccountDetail.tsx` shows the callout under the header, independent of
> whether an alert fired. Verified in a real browser against live,
> backfilled data for Anchor & Ives — see git history for the screenshot
> discussion. The original spec is kept below for context, not because
> anything here is still open.

**Status (historical — see resolution above): not yet implemented — this is
a spec, for whoever picks up frontend work next.** Backend/scoring side
(§5.1) is done, merged, and verified against the live project; nothing here
blocks that. Still outstanding even after the frontend restyle/auth work
(§12) — that pass didn't touch this.

**Why this matters:** `contact_changed` already flows through automatically
wherever an alert is shown today — `alert.signals_fired` renders it as
"Contact Changed" via the existing `formatSignalName` helper
(`frontend/src/lib/format.ts`), same as any other signal, with zero
frontend changes needed for that much (see `AccountDetail.tsx` and
`Alerts.tsx`). But that's a bare label in a list of driver names. A judge
or user seeing "Contact Changed" with no further detail can't verify what
actually happened, which undercuts the explainability standard the rest of
the score already meets (revenue-at-risk in dollars,
`signal_contributions` as a percentage breakdown — see §5). This signal
deserves the same treatment: show the actual fact, not just its name.

**Backend prerequisite (must land first, small):** `GET /accounts/{id}`
currently has nothing to build this from —
`accounts_repo.SIGNAL_SNAPSHOT_COLUMNS` doesn't select
`primary_contact_email`, and `SignalSnapshotOut` (schemas.py) has no field
for it. Add both. Recommended (not required): also add two convenience
fields to `AccountDetail`, computed server-side from `signal_history` so
the frontend doesn't have to walk the array itself —
`contact_changed_at: date | None` and `previous_contact_email: str | None`.

**Frontend requirement:**
1. On `AccountDetail.tsx`, when `contact_changed_at` is present, show a
   visible callout near the account header — not buried in the signal
   grid — e.g. "New point of contact as of {date}: {primary_contact_email}
   (was {previous_contact_email})".
2. Must not depend on an alert having fired. The underlying fact (a contact
   changed) is true regardless of whether it crossed the alert threshold —
   gating it on `signals_fired` would hide it on accounts where it's real
   but didn't (yet) contribute enough to fire.
3. No new sparkline needed. A discrete event doesn't suit the line-chart
   treatment used for the other four continuous signals — a single static
   callout is the more honest representation.
4. Reuse existing style tokens/`formatSignalName` conventions — don't
   invent a new label format just for this one signal.

**Acceptance criteria:**
- Anchor & Ives's account detail page (the seeded demo account, §5.1) shows
  the callout, dated to its final seeded period.
- Every other seeded account (none of which have a contact change) shows no
  callout and no empty/placeholder UI in its place.
- No change to how `signals_fired`/`signal_contributions` render elsewhere.
