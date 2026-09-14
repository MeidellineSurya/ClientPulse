"""POST /score/recompute[/{account_id}]: recomputes baseline, composite
health score, and (if warranted) an alert for one or all accounts, using
the deterministic scoring engine in app/services/scoring_engine.py.

The LLM is never involved in the score or alert decision — see HANDOFF.md
§5. Once an alert fires, app/services/brief_generation.py explains it in
plain language after the fact; it cannot change the score or the decision.
"""

from dataclasses import replace

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.auth import AuthContext, require_auth_context
from app.schemas import AccountScoreResult, RecomputeScoringResponse
from app.services.accounts_repo import fetch_account
from app.services.anomaly_detection import AnomalyModel, fit_anomaly_model, score_anomaly
from app.services.brief_generation import build_alert_brief
from app.services.scoring_engine import (
    SEVERITY_ORDER,
    compute_revenue_at_risk,
    score_account_history,
)
from app.services.scoring_repo import (
    StaleAlertWriteError,
    fetch_accounts_with_contract_value,
    fetch_contract_value,
    fetch_open_alert,
    fetch_signal_history,
    insert_health_score,
    upsert_alert,
    upsert_baselines,
)

router = APIRouter(prefix="/score", tags=["scoring"])


def _score_and_persist(
    client: Client,
    account_id: str,
    history: list[dict],
    contract_value_monthly: float,
    account_name: str,
    anomaly_model: AnomalyModel | None = None,
) -> AccountScoreResult:
    result = score_account_history(history)

    # A separate, complementary ML lens (see anomaly_detection.py) — scored
    # against the most recent raw period, never against drift/baselines, and
    # never allowed to influence result.alert_fired or composite_score.
    # None/None when no model was fit (single-account recompute has no
    # portfolio context to fit one, or the batch endpoint's book is still
    # too small — see anomaly_detection.MIN_TRAINING_ROWS).
    anomaly_score, is_anomaly = score_anomaly(anomaly_model, history[-1])

    upsert_baselines(client, account_id, result.baselines)
    insert_health_score(
        client,
        account_id,
        result.composite_score,
        result.trend_slope,
        anomaly_score=anomaly_score,
        is_anomaly=is_anomaly,
    )
    if result.alert_fired:
        assert result.severity is not None
        existing_alert = fetch_open_alert(client, account_id)
        effective_severity = result.severity
        if existing_alert is not None and SEVERITY_ORDER.index(
            existing_alert["severity"]
        ) > SEVERITY_ORDER.index(result.severity):
            effective_severity = existing_alert["severity"]
        ai_brief, suggested_action = build_alert_brief(
            account_name,
            contract_value_monthly,
            replace(result, severity=effective_severity),
        )
        upsert_alert(
            client,
            account_id,
            result.signals_fired,
            effective_severity,
            ai_brief=ai_brief,
            suggested_action=suggested_action,
            existing_alert=existing_alert,
        )

    return AccountScoreResult(
        account_id=account_id,
        composite_score=result.composite_score,
        trend_slope=result.trend_slope,
        alert_fired=result.alert_fired,
        severity=result.severity,
        signals_fired=result.signals_fired,
        signal_contributions=result.signal_contributions,
        revenue_at_risk=compute_revenue_at_risk(
            contract_value_monthly, result.composite_score
        ),
        anomaly_score=anomaly_score,
        is_anomaly=is_anomaly,
    )


@router.post("/recompute/{account_id}", response_model=AccountScoreResult)
def recompute_account_score(
    account_id: str,
    auth: AuthContext = Depends(require_auth_context),  # noqa: B008 - FastAPI dependency
) -> AccountScoreResult:
    client = auth.client
    account = fetch_account(client, account_id, auth.agency_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    history = fetch_signal_history(client, account_id)
    if not history:
        raise HTTPException(
            status_code=404,
            detail=f"no signal_snapshot history for account {account_id}",
        )
    contract_value_monthly = fetch_contract_value(client, account_id)
    account_name = account["name"]
    try:
        return _score_and_persist(
            client, account_id, history, contract_value_monthly, account_name
        )
    except StaleAlertWriteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/recompute", response_model=RecomputeScoringResponse)
def recompute_all_scores(
    auth: AuthContext = Depends(require_auth_context),  # noqa: B008 - FastAPI dependency
) -> RecomputeScoringResponse:
    client = auth.client
    accounts = fetch_accounts_with_contract_value(client, auth.agency_id)

    # Fetch every account's history up front, in one pass, so the anomaly
    # model can be fit once across the whole book before anyone is scored
    # — an Isolation Forest needs to see the full portfolio to say what's
    # unusual for it, which no per-account call can offer on its own.
    histories: dict[str, list[dict]] = {}
    all_rows: list[dict] = []
    for account_id in accounts:
        history = fetch_signal_history(client, account_id)
        if history:
            histories[account_id] = history
            all_rows.extend(history)
    anomaly_model = fit_anomaly_model(all_rows)

    results = []
    failed_account_ids = []
    for account_id, (contract_value_monthly, account_name) in accounts.items():
        history = histories.get(account_id)
        if not history:
            # New account with no signal_snapshot rows yet — skip
            # rather than fail the whole batch over one account.
            continue
        try:
            results.append(
                _score_and_persist(
                    client,
                    account_id,
                    history,
                    contract_value_monthly,
                    account_name,
                    anomaly_model=anomaly_model,
                )
            )
        except Exception:  # noqa: BLE001 - isolate each account in a batch
            # Isolate one account's bad data (e.g. a malformed
            # signal_snapshot value) or a transient write failure so it
            # can't take down scoring for the rest of the portfolio.
            failed_account_ids.append(account_id)

    return RecomputeScoringResponse(
        accounts_scored=len(results),
        alerts_fired=sum(1 for r in results if r.alert_fired),
        # Only the accounts actually flagged — not every account's
        # proportional exposure — so this reads as "$X across the accounts
        # we've flagged" rather than a fuzzier whole-portfolio total.
        total_revenue_at_risk=round(
            sum(r.revenue_at_risk for r in results if r.alert_fired), 2
        ),
        anomalies_detected=sum(1 for r in results if r.is_anomaly),
        results=results,
        failed_account_ids=failed_account_ids,
    )
