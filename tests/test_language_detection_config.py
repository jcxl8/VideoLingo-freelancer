import unittest
from unittest.mock import patch

from core.utils.config_utils import get_joiner


class LanguageDetectionConfigTest(unittest.TestCase):
    def test_portuguese_detection_uses_space_joiner_instead_of_crashing(self):
        def fake_load_key(key):
            if key == "language_split_with_space":
                return ["en", "ru", "pt"]
            if key == "language_split_without_space":
                return ["zh", "ja"]
            raise KeyError(key)

        with patch("core.utils.config_utils.load_key", side_effect=fake_load_key):
            self.assertEqual(get_joiner("pt"), " ")

    def test_unknown_detected_language_falls_back_to_space_joiner(self):
        def fake_load_key(key):
            if key == "language_split_with_space":
                return ["en", "ru", "pt"]
            if key == "language_split_without_space":
                return ["zh", "ja"]
            raise KeyError(key)

        with patch("core.utils.config_utils.load_key", side_effect=fake_load_key):
            self.assertEqual(get_joiner("xx"), " ")


if __name__ == "__main__":
    unittest.main()
