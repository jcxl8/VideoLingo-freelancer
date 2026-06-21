import unittest


class AsrLanguageOptionsTest(unittest.TestCase):
    def test_asr_options_match_upstream_supported_languages(self):
        from core.st_utils.sidebar_setting import ASR_LANGUAGE_OPTIONS

        self.assertEqual(
            [code for _, code, _ in ASR_LANGUAGE_OPTIONS],
            ["auto", "en", "zh", "es", "ru", "fr", "de", "it", "ja"],
        )

    def test_target_options_keep_customized_language_set(self):
        from core.st_utils.sidebar_setting import TARGET_LANGUAGE_OPTIONS

        self.assertEqual(
            [value for _, value in TARGET_LANGUAGE_OPTIONS],
            ["English", "简体中文", "德语", "俄语", "葡萄牙语"],
        )

    def test_unknown_asr_language_falls_back_to_auto(self):
        from core.st_utils.sidebar_setting import _normalize_asr_language

        self.assertEqual(_normalize_asr_language("pt"), "auto")
        self.assertEqual(_normalize_asr_language("en"), "en")


if __name__ == "__main__":
    unittest.main()
