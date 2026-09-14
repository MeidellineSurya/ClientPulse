# Tests for the portfolio-wide anomaly detection layer — a genuinely
# unsupervised ML model (Isolation Forest), kept separate from and never
# influencing the deterministic scoring engine.

from app.services.anomaly_detection import (
    MIN_TRAINING_ROWS,
    fit_anomaly_model,
    score_anomaly,
)


def _row(resp=3.0, cancelled=0, late=0, scheduled=4) -> dict:
    return {
        "avg_response_time_hours": resp,
        "meetings_cancelled": cancelled,
        "invoice_days_late": late,
        "meetings_scheduled": scheduled,
    }


def _normal_rows(n: int) -> list[dict]:
    # Small, realistic jitter around one "typical" cluster.
    return [
        _row(
            resp=3.0 + (i % 5) * 0.2,
            cancelled=i % 2,
            late=i % 3,
            scheduled=4 - (i % 2),
        )
        for i in range(n)
    ]


def test_fit_returns_none_below_the_minimum_training_size():
    rows = _normal_rows(MIN_TRAINING_ROWS - 1)
    assert fit_anomaly_model(rows) is None


def test_fit_succeeds_at_the_minimum_training_size():
    rows = _normal_rows(MIN_TRAINING_ROWS)
    assert fit_anomaly_model(rows) is not None


def test_score_anomaly_returns_none_none_without_a_model():
    score, is_anomaly = score_anomaly(None, _row())
    assert score is None
    assert is_anomaly is None


def test_score_anomaly_flags_a_wildly_out_of_pattern_row_as_more_anomalous():
    # A tight, clearly-bounded "normal" cluster...
    normal_rows = _normal_rows(50)
    model = fit_anomaly_model(normal_rows)

    # ...versus a period that looks nothing like any of it.
    outlier = _row(resp=300.0, cancelled=40, late=120, scheduled=0)
    typical = _row(resp=3.2, cancelled=0, late=1, scheduled=4)

    outlier_score, _ = score_anomaly(model, outlier)
    typical_score, _ = score_anomaly(model, typical)

    # Lower score = more anomalous, per scikit-learn's own convention.
    assert outlier_score < typical_score


def test_score_anomaly_is_deterministic_across_separate_fits():
    # Same training data fit twice, scored on the same row, must produce
    # the exact same result — an ML feature that isn't reproducible would
    # undermine the rest of this project's determinism story.
    rows = _normal_rows(50)
    row_to_score = _row(resp=50.0, cancelled=10, late=30, scheduled=0)

    model_a = fit_anomaly_model(rows)
    model_b = fit_anomaly_model(rows)

    assert score_anomaly(model_a, row_to_score) == score_anomaly(model_b, row_to_score)


def test_fit_tolerates_a_malformed_value_in_one_row():
    # One bad account's malformed data (e.g. a non-numeric string, which
    # scoring_engine.score_account_history would raise on) must not crash
    # model fitting for the whole portfolio — this fit step runs before
    # recompute_all_scores' per-account failure isolation kicks in.
    rows = _normal_rows(MIN_TRAINING_ROWS) + [
        {**_row(), "avg_response_time_hours": "not-a-number"}
    ]
    model = fit_anomaly_model(rows)
    assert model is not None
    score, is_anomaly = score_anomaly(model, _row())
    assert score is not None


def test_feature_vector_tolerates_missing_signal_values():
    # A row with some signals never populated (None) shouldn't crash the
    # model — treated as 0, same convention as the rest of the scoring
    # pipeline's handling of missing signal_snapshot values.
    rows = _normal_rows(MIN_TRAINING_ROWS)
    incomplete_row = {"avg_response_time_hours": None, "meetings_cancelled": 2}
    model = fit_anomaly_model(rows)
    score, is_anomaly = score_anomaly(model, incomplete_row)
    assert score is not None
    assert is_anomaly is not None
