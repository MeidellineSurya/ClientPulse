# Design reference (unwired)

These files came from the new frontend design mock and are kept verbatim for
reference. Nothing in `src/` imports them.

They implement a **different scoring model** than the real backend
(`backend/app/services/scoring_engine.py`): a client-side *health* score
(higher = better, 4 signals) vs. the backend's *risk* score (higher = worse,
5 signals including `contact_changed`). Per product decision, the backend is
the source of truth for all scoring — these files are not used to compute or
display any real account's score.

- `src/lib/scoring.js` — mock deterministic scoring engine
- `src/data/accounts.seed.js`, `src/data/api.js` — seeded 15-account mock backend
- `ClientPulse-design-reference.html` — standalone interactive visual reference; open directly in a browser

## Known gaps vs. the design brief (deferred, not forgotten)

- **Renewal date**: the design uses a per-account renewal date to drive urgency
  styling and a portfolio "renewals in 90 days" tile. The real schema has no
  such field yet — this is a backend/schema follow-up, not implemented in the UI.
- **Score audit panel**: the design's "how this score was calculated" panel
  needs per-signal drift/contribution data. The real `GET /accounts/:id`
  response doesn't expose `signal_contributions` (only `POST /score/recompute`
  does) — the panel was dropped rather than re-deriving the math client-side.
- **Baseline bands on signal charts**: closed, differently than the design mock
  assumed. No GET endpoint exposes the backend's baseline average/stddev, so
  instead of a literal band the UI derives its own good/watch/bad colour-coding
  client-side from the same `signal_history` array the chart already renders
  (mean/stddev of the visible points — see `signalStatus()` in `src/lib/format.ts`).
  It's a display heuristic, not the deterministic score, and is labelled as such
  wherever it's shown.
