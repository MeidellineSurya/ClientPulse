"""Portfolio-wide anomaly detection — a genuinely unsupervised ML layer
that complements, and never replaces, the deterministic scoring engine.

scoring_engine.py's composite score measures whether an account has
drifted from ITS OWN history — by design, it never compares accounts to
each other (see HANDOFF.md §7). That's the right call for the primary
decision, but it has a real blind spot: a brand-new account has no
established baseline to drift from yet (see
baseline_engine.MIN_BASELINE_SIZE), so a genuinely alarming first few weeks
can't be caught by the per-account approach at all.

This module fills that specific gap with a different, complementary lens:
an Isolation Forest fit across every account's entire signal history,
flagging period/signal combinations that are unusual for the whole book of
business — regardless of what's "normal" for that one account. It never
touches composite_score and cannot itself fire an alert — purely an
additional, clearly-labeled signal for a human to weigh alongside the real
decision.

Unsupervised on purpose: there is no real labeled "did this account
actually churn" outcome to train a predictive classifier against, and
fabricating labels to enable one would be dishonest. An Isolation Forest
needs no labels at all — it profiles what's structurally unusual about a
period's raw signal values relative to the rest of the portfolio.
"""

from dataclasses import dataclass

from sklearn.ensemble import IsolationForest

from app.services.baseline_engine import RAW_SIGNAL_COLUMNS

# Fixed so the exact same input always produces the exact same output —
# an Isolation Forest's tree construction is otherwise randomized per fit,
# which would make this feature non-reproducible between runs.
RANDOM_STATE = 42

# Below this many training rows, a forest has too little data to say
# anything meaningful — skip anomaly detection for a young/small book
# rather than report a number built on almost nothing.
MIN_TRAINING_ROWS = 20


def _safe_float(value: object) -> float:
    # A malformed signal_snapshot value (e.g. a non-numeric string) must not
    # take down anomaly detection for the whole portfolio just because one
    # account's data is bad — scoring_engine.score_account_history would
    # raise on the same row too, but that failure is isolated per-account
    # by the caller (see scoring.py's recompute_all_scores); this fit step
    # runs before that isolation, across every account at once.
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _feature_vector(row: dict) -> list[float]:
    return [_safe_float(row.get(signal)) for signal in RAW_SIGNAL_COLUMNS]


@dataclass(frozen=True)
class AnomalyModel:
    forest: IsolationForest


def fit_anomaly_model(all_history_rows: list[dict]) -> AnomalyModel | None:
    """Fits one Isolation Forest across every account's full signal
    history (every period, every account — the one place in this codebase
    that deliberately looks across the whole portfolio at once). Returns
    None when there isn't enough data yet to fit anything meaningful.
    """
    if len(all_history_rows) < MIN_TRAINING_ROWS:
        return None
    features = [_feature_vector(row) for row in all_history_rows]
    forest = IsolationForest(random_state=RANDOM_STATE)
    forest.fit(features)
    return AnomalyModel(forest=forest)


def score_anomaly(
    model: AnomalyModel | None, latest_row: dict
) -> tuple[float | None, bool | None]:
    """Returns (anomaly_score, is_anomaly) for one period's raw signal
    values against the fitted portfolio-wide model. Higher anomaly_score
    means more normal, consistent with scikit-learn's own convention;
    is_anomaly is the forest's own inlier/outlier call. (None, None) when
    no model could be fit — see fit_anomaly_model.
    """
    if model is None:
        return None, None
    vector = [_feature_vector(latest_row)]
    anomaly_score = round(float(model.forest.decision_function(vector)[0]), 4)
    is_anomaly = bool(model.forest.predict(vector)[0] == -1)
    return anomaly_score, is_anomaly
