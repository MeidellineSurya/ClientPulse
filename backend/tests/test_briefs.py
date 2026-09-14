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

    def test_unsupported_certainty_claim_uses_fallback(self):
        for summary in (
            "Risk is definitely caused by incompetence.",
            "The relationship has certainly ended.",
            "This has proven fatal to the account.",
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

    def test_causal_connector_language_is_permitted(self):
        # These connectors merely tie cited evidence to the score, which is
        # exactly what the prompt asks for — they shouldn't trigger fallback.
        for summary in (
            "The risk is elevated due to slow responses.",
            "Payment delays led to the elevated risk.",
            "Cancelled meetings caused the score to worsen.",
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

                self.assertEqual(brief.source, "llm")

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

    def test_context_defaults_to_no_raw_values_or_score_labels(self):
        # Existing callers (e.g. retention_radar.service) don't know about
        # raw values or score-tier labels — must keep working unchanged.
        context = self._context()
        self.assertEqual(context.signal_current_values, {})
        self.assertEqual(context.signal_baseline_averages, {})
        self.assertIsNone(context.recent_score_labels)

    def test_context_rejects_mismatched_score_label_count(self):
        with self.assertRaisesRegex(ValueError, "recent_score_labels"):
            BriefContext(
                account_name="StudioCo",
                monthly_value=10_000,
                composite_risk=0.82,
                severity="high",
                triggered_signals={"response_time": 0.88},
                recent_scores=(0.54, 0.67, 0.82),
                recent_score_labels=("watch", "at-risk"),  # only 2, needs 3
            )

    def test_context_rejects_non_finite_raw_value(self):
        with self.assertRaisesRegex(ValueError, "signal_current_values"):
            BriefContext(
                account_name="StudioCo",
                monthly_value=10_000,
                composite_risk=0.82,
                severity="high",
                triggered_signals={"response_time": 0.88},
                recent_scores=(0.54, 0.67, 0.82),
                signal_current_values={"response_time": float("inf")},
            )

    def test_prompt_cites_raw_values_and_score_labels_when_present(self):
        context = BriefContext(
            account_name="StudioCo",
            monthly_value=10_000,
            composite_risk=0.82,
            severity="high",
            triggered_signals={"avg_response_time_hours": 0.88},
            recent_scores=(0.2, 0.55, 0.82),
            signal_current_values={"avg_response_time_hours": 14.2},
            signal_baseline_averages={"avg_response_time_hours": 3.1},
            recent_score_labels=("healthy", "watch", "at-risk"),
        )
        provider = StubProvider(
            {
                "summary": "StudioCo's response times have climbed sharply.",
                "drivers": ["Response time is now 14.2 hours, usually 3.1."],
                "suggested_action": "Schedule an internal review.",
            }
        )

        generate_brief(context, provider)

        prompt = provider.prompts[0]
        self.assertIn("14.2", prompt)
        self.assertIn("3.1", prompt)
        self.assertIn("healthy", prompt)
        self.assertIn("at-risk", prompt)

    def test_fallback_cites_raw_values_when_present(self):
        context = BriefContext(
            account_name="StudioCo",
            monthly_value=10_000,
            composite_risk=0.82,
            severity="high",
            triggered_signals={"avg_response_time_hours": 0.88},
            recent_scores=(0.2, 0.55, 0.82),
            signal_current_values={"avg_response_time_hours": 14.2},
            signal_baseline_averages={"avg_response_time_hours": 3.1},
        )

        class FailingProvider:
            def generate(self, prompt):
                raise TimeoutError("provider unavailable")

        brief = generate_brief(context, FailingProvider())

        self.assertEqual(brief.source, "fallback")
        self.assertIn("14.2", brief.drivers[0])
        self.assertIn("3.1", brief.drivers[0])
        self.assertNotIn("drift is", brief.drivers[0])


if __name__ == "__main__":
    unittest.main()
