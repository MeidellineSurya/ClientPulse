"""Computes each account's own rolling per-signal baseline (mean + stddev)
from its signal_snapshot history — the "what's normal for this client"
that scoring_engine.py measures drift against.

Every account is scored against its own history, never a portfolio-wide
average (see HANDOFF.md §7) — that's the whole reason this module takes a
single account's history and nothing else.
"""

from statistics import fmean, stdev

TRACKED_SIGNALS = [
    "avg_response_time_hours",
    "meetings_cancelled",
    "invoice_days_late",
    "meetings_scheduled",
]

# Most-recent periods held out of the baseline and used for the
# worsening-trend check instead — keeps the baseline from being polluted by
# the exact weeks scoring is trying to evaluate.
TREND_WINDOW = 3

# A baseline computed from fewer than this many points can't establish any
# real variance (1 point always has stddev=None) — see
# split_baseline_and_trend_windows.
MIN_BASELINE_SIZE = 2


def mean_stddev(values: list[float]) -> tuple[float, float | None]:
    """Sample mean/stddev. stddev is None with fewer than 2 values — not
    enough history yet to say what "normal variance" looks like."""
    n = len(values)
    if n == 0:
        return 0.0, None
    avg = fmean(values)
    if n < 2:
        return avg, None
    return avg, stdev(values)


def split_baseline_and_trend_windows(history: list[dict]) -> tuple[list[dict], list[dict]]:
    """Splits period-ordered (oldest first) signal_snapshot history into
    (baseline_window, trend_window).

    Falls back to using all of `history` for both windows whenever the
    baseline_window would otherwise end up with fewer than MIN_BASELINE_SIZE
    points (a new account, or one with exactly TREND_WINDOW+1 periods) —
    drift detection is naturally weaker until more history accumulates, but
    this avoids scoring off a baseline too thin to have any established
    variance (a single-point baseline always has stddev=None, which
    compute_drift treats as "any deviation is maximal" — noisy and prone to
    false alerts rather than a real trend).
    """
    if len(history) - TREND_WINDOW < MIN_BASELINE_SIZE:
        return history, history
    return history[:-TREND_WINDOW], history[-TREND_WINDOW:]


def compute_baselines(baseline_window: list[dict]) -> dict[str, tuple[float, float | None]]:
    """Per-signal (rolling_avg, rolling_stddev) computed from baseline_window."""
    baselines = {}
    for signal in TRACKED_SIGNALS:
        values = [float(row[signal]) for row in baseline_window if row.get(signal) is not None]
        baselines[signal] = mean_stddev(values)
    return baselines
