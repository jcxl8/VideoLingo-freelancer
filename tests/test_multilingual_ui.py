import unittest
from unittest.mock import patch

from translations import translations


EXPECTED_LANGUAGES = {
    "🇬🇧 English": "en",
    "🇨🇳 简体中文": "zh-CN",
    "🇪🇸 Español": "es",
    "🇷🇺 Русский": "ru",
    "🇫🇷 Français": "fr",
    "🇩🇪 Deutsch": "de",
    "🇮🇹 Italiano": "it",
    "🇯🇵 日本語": "ja",
}


class MultilingualUiTest(unittest.TestCase):
    def test_selector_exposes_approved_languages(self):
        self.assertEqual(translations.DISPLAY_LANGUAGES, EXPECTED_LANGUAGES)

    def test_missing_localized_key_falls_back_to_english(self):
        catalogs = {
            "de": {},
            "en": {"fallback-probe": "English fallback"},
        }
        with patch(
            "core.utils.config_utils.load_key", return_value="de"
        ), patch.object(
            translations,
            "load_translations",
            side_effect=lambda language="en": catalogs.get(language, {}),
        ):
            self.assertEqual(
                translations.translate("fallback-probe"),
                "English fallback",
            )

    def test_unknown_key_falls_back_to_original_key(self):
        with patch(
            "core.utils.config_utils.load_key", return_value="it"
        ), patch.object(translations, "load_translations", return_value={}):
            self.assertEqual(
                translations.translate("missing-test-key"),
                "missing-test-key",
            )


if __name__ == "__main__":
    unittest.main()
