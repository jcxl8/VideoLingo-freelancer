import unittest
from unittest.mock import patch

from core import translate_lines


class TranslatorHealthTest(unittest.TestCase):
    def setUp(self):
        translate_lines.TRANSLATOR_HEALTH_CACHE.clear()

    def test_models_url_normalises_openai_base_url(self):
        self.assertEqual(
            translate_lines._translator_models_url("http://127.0.0.1:8765/v1"),
            "http://127.0.0.1:8765/v1/models",
        )
        self.assertEqual(
            translate_lines._translator_models_url("http://127.0.0.1:8765/v1/chat/completions"),
            "http://127.0.0.1:8765/v1/models",
        )

    def test_unavailable_local_translator_is_cached_false(self):
        values = {
            "translator_api.base_url": "http://127.0.0.1:8765/v1",
            "translator_api.model": "hy-mt2-7b",
            "translator_api.key": "sk-local",
        }

        def fake_load_key(key):
            return values[key]

        with patch.object(translate_lines, "load_key", side_effect=fake_load_key):
            with patch.object(translate_lines, "is_local_translator", return_value=True):
                with patch.object(translate_lines.urllib.request, "urlopen", side_effect=OSError("connection refused")) as urlopen:
                    self.assertFalse(translate_lines._local_translator_available())
                    self.assertFalse(translate_lines._local_translator_available())

        urlopen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
