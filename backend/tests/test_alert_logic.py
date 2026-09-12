import unittest
from datetime import datetime, timedelta, timezone

from retention_radar.alerts import HealthScore, evaluate_alert


class AlertEvaluationTests(unittest.TestCase):
    def test_crossing_threshold_with_three_worsening_periods_fires(self):
        history = [
            HealthScore(
                "acct-1",
                datetime(2026, 9, 1, tzinfo=timezone.utc),
                0.48,
                {"response_time": 0.50},
            ),
            HealthScore(
                "acct-1",
                datetime(2026, 9, 8, tzinfo=timezone.utc),
                0.59,
                {"response_time": 0.65},
            ),
            HealthScore(
                "acct-1",
                datetime(2026, 9, 15, tzinfo=timezone.utc),
                0.72,
                {"response_time": 0.81},
            ),
        ]

        result = evaluate_alert(history, threshold=0.65)

        self.assertTrue(result.should_alert)
        self.assertEqual(result.severity, "medium")
        self.assertEqual(result.signals_fired, ("response_time",))

    def test_threshold_crossing_without_three_worsening_periods_does_not_fire(self):
        history = [
            HealthScore("acct-1", datetime(2026, 9, 1, tzinfo=timezone.utc), 0.61, {}),
            HealthScore("acct-1", datetime(2026, 9, 8, tzinfo=timezone.utc), 0.60, {}),
            HealthScore("acct-1", datetime(2026, 9, 15, tzinfo=timezone.utc), 0.70, {}),
        ]

        result = evaluate_alert(history)

        self.assertFalse(result.should_alert)
        self.assertEqual(result.reason, "threshold_and_trend_not_met")

    def test_worsening_below_threshold_does_not_fire(self):
        history = [
            HealthScore("acct-1", datetime(2026, 9, 1, tzinfo=timezone.utc), 0.30, {}),
            HealthScore("acct-1", datetime(2026, 9, 8, tzinfo=timezone.utc), 0.40, {}),
            HealthScore("acct-1", datetime(2026, 9, 15, tzinfo=timezone.utc), 0.50, {}),
        ]

        result = evaluate_alert(history)

        self.assertFalse(result.should_alert)
        self.assertEqual(result.reason, "threshold_and_trend_not_met")

    def test_existing_episode_key_suppresses_duplicate_alert(self):
        history = [
            HealthScore("acct-1", datetime(2026, 9, 1, tzinfo=timezone.utc), 0.48, {}),
            HealthScore("acct-1", datetime(2026, 9, 8, tzinfo=timezone.utc), 0.59, {}),
            HealthScore("acct-1", datetime(2026, 9, 15, tzinfo=timezone.utc), 0.72, {}),
        ]
        episode_key = "acct-1:2026-09-15T00:00:00+00:00"

        result = evaluate_alert(
            history, threshold=0.65, alerted_episode_keys={episode_key}
        )

        self.assertFalse(result.should_alert)
        self.assertEqual(result.reason, "episode_already_alerted")

    def test_episode_key_normalizes_timestamp_to_utc(self):
        aest = timezone(timedelta(hours=10))
        history = [
            HealthScore("acct-1", datetime(2026, 9, 1, 10, tzinfo=aest), 0.48, {}),
            HealthScore("acct-1", datetime(2026, 9, 8, 10, tzinfo=aest), 0.59, {}),
            HealthScore("acct-1", datetime(2026, 9, 15, 10, tzinfo=aest), 0.72, {}),
        ]
        utc_key = "acct-1:2026-09-15T00:00:00+00:00"

        result = evaluate_alert(history, alerted_episode_keys={utc_key})

        self.assertFalse(result.should_alert)
        self.assertEqual(result.reason, "episode_already_alerted")

    def test_mixed_account_history_is_rejected(self):
        history = [
            HealthScore("acct-1", datetime(2026, 9, 1, tzinfo=timezone.utc), 0.48, {}),
            HealthScore("acct-2", datetime(2026, 9, 8, tzinfo=timezone.utc), 0.59, {}),
            HealthScore("acct-1", datetime(2026, 9, 15, tzinfo=timezone.utc), 0.72, {}),
        ]

        with self.assertRaisesRegex(ValueError, "one account"):
            evaluate_alert(history)

    def test_threshold_outside_unit_interval_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "threshold"):
            evaluate_alert([], threshold=1.01)

    def test_health_score_rejects_non_finite_or_out_of_range_risk(self):
        for invalid in (-0.01, 1.01, float("nan"), float("inf")):
            with (
                self.subTest(invalid=invalid),
                self.assertRaisesRegex(ValueError, "composite_risk"),
            ):
                HealthScore(
                    "acct-1",
                    datetime(2026, 9, 1, tzinfo=timezone.utc),
                    invalid,
                    {},
                )

    def test_health_score_rejects_invalid_signal_drift(self):
        for invalid in (float("nan"), "high"):
            with (
                self.subTest(invalid=invalid),
                self.assertRaisesRegex(ValueError, "signal drift"),
            ):
                HealthScore(
                    "acct-1",
                    datetime(2026, 9, 1, tzinfo=timezone.utc),
                    0.7,
                    {"response_time": invalid},  # type: ignore[dict-item]
                )

    def test_health_score_requires_timezone_aware_timestamp(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            HealthScore("acct-1", datetime(2026, 9, 1), 0.7, {})  # noqa: DTZ001

    def test_alert_history_requires_distinct_period_timestamps(self):
        repeated = datetime(2026, 9, 1, tzinfo=timezone.utc)
        history = [
            HealthScore("acct-1", repeated, 0.48, {}),
            HealthScore("acct-1", repeated, 0.59, {}),
            HealthScore("acct-1", datetime(2026, 9, 15, tzinfo=timezone.utc), 0.72, {}),
        ]

        with self.assertRaisesRegex(ValueError, "distinct period"):
            evaluate_alert(history)


if __name__ == "__main__":
    unittest.main()
