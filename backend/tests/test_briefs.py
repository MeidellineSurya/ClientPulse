import unittest

from retention_radar.briefs import BriefContext, generate_brief


class StubProvider:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.response


class BriefGenerationTests(unittest.TestCase):
    def _context(self):
        return BriefContext(
            account_name="StudioCo",
            monthly_value=10_000,
            composite_risk=0.82,
            severity="high",
            triggered_signals={"response_time": 0.88, "meeting_cancellations": 0.75},
            recent_scores=(0.54, 0.67, 0.82),
        )

    def test_valid_provider_response_becomes_a_validated_brief(self):
        context = self._context()
        provider = StubProvider(
            {
                "summary": "StudioCo's relationship health has worsened across three periods.",
                "drivers": [
                    "Response time drift is the strongest signal.",
                    "Meeting cancellations also increased.",
                ],
                "suggested_action": "Schedule an internal account review before contacting the client.",
            }
        )

        brief = generate_brief(context, provider)

        self.assertEqual(brief.source, "llm")
        self.assertEqual(len(brief.drivers), 2)
        self.assertIn("StudioCo", brief.summary)
        self.assertIn("The risk score is authoritative", provider.prompts[0])

    def test_provider_failure_returns_deterministic_fallback(self):
        class FailingProvider:
            def generate(self, prompt):
                raise TimeoutError("provider unavailable")

        brief = generate_brief(self._context(), FailingProvider())

        self.assertEqual(brief.source, "fallback")
        self.assertIn("StudioCo", brief.summary)
        self.assertIn("82%", brief.summary)
        self.assertIn("response time", brief.drivers[0].lower())

    def test_malformed_provider_response_uses_fallback(self):
        provider = StubProvider({"summary": "Missing required fields"})

        brief = generate_brief(self._context(), provider)

        self.assertEqual(brief.source, "fallback")
        self.assertIn("StudioCo", brief.summary)

    def test_policy_violating_provider_response_uses_fallback(self):
        for action in (
            "Immediately contact the client.",
            "Email the client immediately.",
            "Automatically send the client an email.",
        ):
            with self.subTest(action=action):
                provider = StubProvider(
                    {
                        "summary": "Risk crossed the threshold after a worsening trend.",
                        "drivers": ["Response-time drift is elevated."],
                        "suggested_action": action,
                    }
                )

                brief = generate_brief(self._context(), provider)

                self.assertEqual(brief.source, "fallback")

    def test_unsupported_causal_claim_uses_fallback(self):
        for summary in (
            "Risk is definitely caused by incompetence.",
            "Payment delays led to the elevated risk.",
            "The risk is elevated due to slow responses.",
        ):
            with self.subTest(summary=summary):
                provider = StubProvider(
                    {
                        "summary": summary,
                        "drivers": ["Response-time drift is elevated."],
                        "suggested_action": "Review the account internally.",
                    }
                )

                brief = generate_brief(self._context(), provider)

                self.assertEqual(brief.source, "fallback")

    def test_context_rejects_non_string_signal_names(self):
        with self.assertRaisesRegex(ValueError, "signal name"):
            BriefContext(
                account_name="StudioCo",
                monthly_value=10_000,
                composite_risk=0.82,
                severity="high",
                triggered_signals={1: 0.84},  # type: ignore[dict-item]
                recent_scores=(0.61, 0.70, 0.82),
            )

    def test_context_rejects_risk_outside_unit_interval(self):
        with self.assertRaisesRegex(ValueError, "composite_risk"):
            BriefContext(
                account_name="StudioCo",
                monthly_value=10_000,
                composite_risk=1.2,
                severity="critical",
                triggered_signals={},
                recent_scores=(0.7, 0.9, 1.2),
            )


if __name__ == "__main__":
    unittest.main()
