# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary user: **account managers at retainer-based marketing/creative agencies**. Their job is to review a portfolio of client accounts (typically each morning) and catch relationship drift — slower replies, more cancelled meetings, later invoice payments — before a client raises it or churns at renewal.

## Product Purpose

ClientPulse is a behavioral churn early-warning tool for retainer-based agencies. It watches communication and billing behavior an agency already has access to (Gmail, Calendar, invoices) and flags accounts that are quietly drifting toward churn, weeks before anyone says anything. Success is an account manager acting on a flagged account in time to save the retainer.

## Positioning

Existing AI churn-prediction tools (Gainsight, ChurnZero, Pendo) require product-usage data — telemetry from a SaaS product. Agencies don't have that; their "product" is a relationship, not software. ClientPulse's mechanism is different: it derives risk from behavioral signals agencies already generate (email response time, meeting cancellations, invoice lateness, point-of-contact turnover), and it baselines each account against *its own* rolling history rather than a portfolio-wide average — a client's "normal" is whatever is normal for that client.

## Operating Context

- **Portfolio view**: the morning check — all accounts sorted by risk, with total revenue-at-risk surfaced at the top.
- **Account detail**: per-signal trend charts and a composite risk-score-over-time chart, plus an AI-generated brief explaining exactly which signals drove a flag (via Groq, citing real `signal_contributions`).
- **Alerts inbox**: the working queue an account manager triages and updates status on.
- **Connections**: Gmail/Calendar OAuth ingestion (metadata-only — response times and meeting activity, not email content) and CSV upload as a stand-in for a live accounting/Xero integration.
- Ingestion and scoring run as backend jobs (`/score/recompute`); the frontend is a read/act surface over that data, not where computation happens.

## Capabilities and Constraints

- **No client-facing automation.** The system only alerts internal agency staff — it never contacts a client directly. This is a deliberate, durable constraint (liability/trust), not a current-scope limitation to relax later.
- **Deterministic, explainable scoring**, not a black-box model — every alert can cite the specific signal contributions behind it. This explainability is a product commitment, not just an implementation detail.
- **Per-account baselining** — the drift formula divides by that account's own rolling standard deviation, never a global/portfolio benchmark.
- **CSV upload stands in for a live accounting integration** (e.g. Xero) — known scope limitation, not a design assumption to build around as permanent.
- **Email/calendar data is metadata-only** — response timing and meeting activity, never message content. No client consent/data-scoping flow exists yet for this; that gap should be stated rather than hidden if it comes up in user-facing copy.
- Live Gmail/Calendar verification against a real Google project is not yet done (implementation exists; only credentialed verification is pending).

## Brand Commitments

- Current binding product name: **ClientPulse** (matches the live repo, README, and deployed URLs). The codebase also contains legacy names from earlier hackathon phases — "Retention Radar" (internal build name) and "Rapport" (a pitch-facing name) — in HANDOFF.md; these are historical, not current branding, and should not resurface in new user-facing work.
- Existing frontend visual system: a custom flat "Modernist" system (zero border-radius, ink-on-light-ground, single red accent) — already implemented, documented separately in `frontend/reference/README.md`. This is visual-system evidence for `/impeccable document`, not restated here.

## Evidence on Hand

- The product runs against a real, live Supabase project with **seeded demo data**: 15 accounts, 120 `signal_snapshot` rows, and a demo run producing 3 fired alerts totaling $418,369.20 in revenue at risk.
- **This is still a demo/illustrative stage product** — the accounts, history, and dollar figures are seeded for demonstration, not real agency customers. Future design and product work should keep treating this data as illustrative and must not fabricate real customer testimonials, logos, case studies, or production-scale claims on top of it.
- A rehearsed demo script exists (HANDOFF.md §9): Portfolio → flagged account detail → Alerts inbox → ROI framing (one saved $10K/month account ≈ $140K avoided against a $150–300/month price tag). Treat the price tag as a pitch anchor, not a confirmed pricing model.

## Product Principles

1. Use data the agency already has — no new product-usage instrumentation required from the client.
2. Every account's "normal" is its own baseline; never compare across the portfolio.
3. Alert internally, never automate outward — a human always decides whether and how to act.
4. Every flag must be explainable in plain terms an account manager would use, citing the real signals behind it.
5. Surface drift early — the value is entirely in the lead time before a renewal conversation, not after.
