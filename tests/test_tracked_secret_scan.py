import unittest


class TrackedSecretScanTest(unittest.TestCase):
    def test_placeholders_and_local_sentinel_are_allowed(self):
        from scripts.check_tracked_secrets import scan_text

        text = "api:\n  key: YOUR_API_KEY\ntranslator_api:\n  key: sk-local\n"

        self.assertEqual(scan_text("config.yaml", text), [])

    def test_api_token_is_reported_without_value(self):
        from scripts.check_tracked_secrets import scan_text

        secret = "sk-" + "a" * 32
        findings = scan_text("config.yaml", f"api:\n  key: {secret}\n")

        self.assertEqual(findings, ["probable API token"])
        self.assertNotIn(secret, repr(findings))

    def test_private_cookie_path_is_reported_without_path(self):
        from scripts.check_tracked_secrets import scan_text

        private_path = "/Users/example/Downloads/browser-cookies.txt"
        findings = scan_text(
            "config.yaml", f"youtube:\n  cookies_path: {private_path}\n"
        )

        self.assertEqual(findings, ["non-placeholder cookie path"])
        self.assertNotIn(private_path, repr(findings))

    def test_secret_toml_assignment_is_reported(self):
        from scripts.check_tracked_secrets import scan_text

        findings = scan_text(
            "settings.toml", 'VIDEOLINGO_API_KEY = "private-value"\n'
        )

        self.assertEqual(findings, ["local secret assignment"])


if __name__ == "__main__":
    unittest.main()
