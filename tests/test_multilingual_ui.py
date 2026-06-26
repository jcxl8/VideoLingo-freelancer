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

    def test_each_selected_language_has_valid_catalog(self):
        translations.load_translations.cache_clear()
        for code in EXPECTED_LANGUAGES.values():
            with self.subTest(code=code):
                catalog = translations.load_translations(code)
                self.assertIsInstance(catalog, dict)
                self.assertTrue(catalog, code)

    def test_streamlit_buttons_use_current_width_api(self):
        for path in ("st.py", "core/st_utils/download_video_section.py", "core/st_utils/sidebar_setting.py"):
            with self.subTest(path=path):
                text = __import__("pathlib").Path(path).read_text(encoding="utf-8")
                self.assertNotIn("use_container_width=True", text)


if __name__ == "__main__":
    unittest.main()
