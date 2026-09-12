"""POST /score/recompute[/{account_id}]: recomputes baseline, composite
health score, and (if warranted) an alert for one or all accounts, using
the deterministic scoring engine in app/services/scoring_engine.py.

The LLM is never involved here — see HANDOFF.md §5. This endpoint only
decides the number; a later step (Groq brief generation) explains it in
plain language after the fact.
"""

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.db import get_supabase_client
from app.schemas import AccountScoreResult, RecomputeScoringResponse
from app.services.scoring_engine import compute_revenue_at_risk, score_account_history
from app.services.scoring_repo import (
    fetch_accounts_with_contract_value,
    fetch_contract_value,
    fetch_signal_history,
    insert_health_score,
    upsert_alert,
    upsert_baselines,
)

router = APIRouter(prefix="/score", tags=["scoring"])


def _require_supabase_client() -> Client:
    # Wraps get_supabase_client() so a missing SUPABASE_* config surfaces as
    # a clean 503 instead of an unhandled 500 (same pattern as app/routers/ingest.py).
    try:
        return get_supabase_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _score_and_persist(
    client: Client, account_id: str, history: list[dict], contract_value_monthly: float
) -> AccountScoreResult:
    result = score_account_history(history)

    upsert_baselines(client, account_id, result.baselines)
    insert_health_score(client, account_id, result.composite_score, result.trend_slope)
    if result.alert_fired:
        upsert_alert(client, account_id, result.signals_fired, result.severity)

    return AccountScoreResult(
        account_id=account_id,
        composite_score=result.composite_score,
        trend_slope=result.trend_slope,
        alert_fired=result.alert_fired,
        severity=result.severity,
        signals_fired=result.signals_fired,
        signal_contributions=result.signal_contributions,
        revenue_at_risk=compute_revenue_at_risk(contract_value_monthly, result.composite_score),
    )


@router.post("/recompute/{account_id}", response_model=AccountScoreResult)
def recompute_account_score(
    account_id: str, client: Client = Depends(_require_supabase_client)
) -> AccountScoreResult:
    history = fetch_signal_history(client, account_id)
    if not history:
        raise HTTPException(status_code=404, detail=f"no signal_snapshot history for account {account_id}")
    contract_value_monthly = fetch_contract_value(client, account_id)
    return _score_and_persist(client, account_id, history, contract_value_monthly)


@router.post("/recompute", response_model=RecomputeScoringResponse)
def recompute_all_scores(client: Client = Depends(_require_supabase_client)) -> RecomputeScoringResponse:
    results = []
    for account_id, contract_value_monthly in fetch_accounts_with_contract_value(client).items():
        history = fetch_signal_history(client, account_id)
        if not history:
            # New account with no signal_snapshot rows yet — skip rather
            # than fail the whole batch over one account.
            continue
        results.append(_score_and_persist(client, account_id, history, contract_value_monthly))

    return RecomputeScoringResponse(
        accounts_scored=len(results),
        alerts_fired=sum(1 for r in results if r.alert_fired),
        # Only the accounts actually flagged — not every account's
        # proportional exposure — so this reads as "$X across the accounts
        # we've flagged" rather than a fuzzier whole-portfolio total.
        total_revenue_at_risk=round(sum(r.revenue_at_risk for r in results if r.alert_fired), 2),
        results=results,
    )
