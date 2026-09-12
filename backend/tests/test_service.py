import unittest
from datetime import datetime, timezone

from retention_radar.alerts import HealthScore
from retention_radar.service import build_alert


class Provider:
    def __init__(self):
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        return {
            "summary": "StudioCo shows a sustained worsening retention trend.",
            "drivers": ["Response time is the strongest drift signal."],
            "suggested_action": "Review the account internally.",
        }


class AlertServiceTests(unittest.TestCase):
    def test_build_alert_combines_deterministic_decision_with_brief(self):
        history = [
            HealthScore(
                "acct-1",
                datetime(2026, 9, 1, tzinfo=timezone.utc),
                0.48,
                {"response_time": 0.51},
            ),
            HealthScore(
                "acct-1",
                datetime(2026, 9, 8, tzinfo=timezone.utc),
                0.59,
                {"response_time": 0.66},
            ),
            HealthScore(
                "acct-1",
                datetime(2026, 9, 15, tzinfo=timezone.utc),
                0.82,
                {"response_time": 0.88},
            ),
        ]
        provider = Provider()

        result = build_alert(
            history, account_name="StudioCo", monthly_value=10_000, provider=provider
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.decision.severity, "high")
        self.assertEqual(result.brief.source, "llm")
        self.assertEqual(provider.calls, 1)

    def test_build_alert_does_not_call_provider_when_policy_does_not_fire(self):
        history = [
            HealthScore("acct-1", datetime(2026, 9, 1, tzinfo=timezone.utc), 0.40, {}),
            HealthScore("acct-1", datetime(2026, 9, 8, tzinfo=timezone.utc), 0.50, {}),
            HealthScore("acct-1", datetime(2026, 9, 15, tzinfo=timezone.utc), 0.60, {}),
        ]
        provider = Provider()

        result = build_alert(
            history, account_name="StudioCo", monthly_value=10_000, provider=provider
        )

        self.assertIsNone(result)
        self.assertEqual(provider.calls, 0)


if __name__ == "__main__":
    unittest.main()
