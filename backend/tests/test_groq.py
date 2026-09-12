import json
import unittest

from retention_radar.groq import GroqBriefProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class GroqProviderTests(unittest.TestCase):
    def test_generate_calls_openai_compatible_endpoint_and_parses_json_content(self):
        captured = {}

        def opener(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "summary": "Account risk is worsening.",
                                        "drivers": ["Response time drift increased."],
                                        "suggested_action": "Review the account internally.",
                                    }
                                )
                            }
                        }
                    ],
                }
            )

        provider = GroqBriefProvider(api_key="test-key", opener=opener, timeout=7)
        result = provider.generate("evidence prompt")

        self.assertEqual(result["summary"], "Account risk is worsening.")
        self.assertEqual(captured["timeout"], 7)
        self.assertEqual(
            captured["request"].full_url,
            "https://api.groq.com/openai/v1/chat/completions",
        )
        self.assertEqual(
            captured["request"].get_header("Authorization"), "Bearer test-key"
        )
        body = json.loads(captured["request"].data)
        self.assertEqual(body["model"], "openai/gpt-oss-120b")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertIn("untrusted data", body["messages"][0]["content"])
        self.assertEqual(
            body["messages"][1], {"role": "user", "content": "evidence prompt"}
        )


if __name__ == "__main__":
    unittest.main()
