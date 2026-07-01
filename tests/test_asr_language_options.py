import unittest


class AsrLanguageOptionsTest(unittest.TestCase):
    def test_asr_options_match_upstream_supported_languages(self):
        from core.st_utils.sidebar_setting import ASR_LANGUAGE_OPTIONS

        self.assertEqual(
            [code for _, code, _ in ASR_LANGUAGE_OPTIONS],
            ["auto", "en", "zh", "es", "ru", "fr", "de", "it", "ja", "ko"],
        )

    def test_target_options_keep_customized_language_set(self):
        from core.st_utils.sidebar_setting import TARGET_LANGUAGE_OPTIONS

        self.assertEqual(
            [value for _, value in TARGET_LANGUAGE_OPTIONS],
            ["English", "简体中文", "西班牙语", "日语", "韩语", "德语", "俄语", "葡萄牙语"],
        )

    def test_unknown_asr_language_uses_manual_input_state(self):
        from core.st_utils.sidebar_setting import (
            MANUAL_LANGUAGE_VALUE,
            _source_language_select_state,
        )

        _, values, selected_index, custom_value = _source_language_select_state("pt")

        self.assertEqual(values[selected_index], MANUAL_LANGUAGE_VALUE)
        self.assertEqual(custom_value, "pt")

    def test_unknown_target_language_uses_manual_input_state(self):
        from core.st_utils.sidebar_setting import (
            MANUAL_LANGUAGE_VALUE,
            _target_language_select_state,
        )

        _, values, selected_index, custom_value = _target_language_select_state("越南语")

        self.assertEqual(values[selected_index], MANUAL_LANGUAGE_VALUE)
        self.assertEqual(custom_value, "越南语")


if __name__ == "__main__":
    unittest.main()
