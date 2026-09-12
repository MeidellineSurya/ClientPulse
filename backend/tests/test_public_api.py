import unittest


class PublicApiTests(unittest.TestCase):
    def test_package_exports_backend_integration_entrypoints(self):
        from retention_radar import GroqBriefProvider, HealthScore, build_alert

        self.assertTrue(callable(build_alert))
        self.assertTrue(callable(HealthScore))
        self.assertTrue(callable(GroqBriefProvider))


if __name__ == "__main__":
    unittest.main()
