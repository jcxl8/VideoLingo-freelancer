import json
import unittest
from pathlib import Path

import yaml


class PortraitSidebarConfigTest(unittest.TestCase):
    PORTRAIT_KEYS = (
        "portrait_source_font_size",
        "portrait_translation_font_size",
        "portrait_hardsub_translation_font_size",
        "portrait_bilingual_offset",
        "portrait_hardsub_translation_offset",
        "portrait_watermark_font_size",
        "portrait_watermark_offset",
    )
    REQUIRED_LABELS = (
        "9:16 Portrait Subtitle Settings",
        "Portrait Source Font Size",
        "Portrait Translation Font Size",
        "Portrait Bilingual Offset",
        "Portrait Hard Subtitle Translation Font Size",
        "Portrait Hard Subtitle Translation Offset",
        "Portrait Watermark Font Size",
        "Portrait Watermark Offset",
        "Portrait font sizes use a 576px-wide reference",
        "The encoded source hard-subtitle font cannot be changed",
    )

    def setUp(self):
        self.config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
        self.sidebar = Path("core/st_utils/sidebar_setting.py").read_text(encoding="utf-8")
        self.st_source = Path("st.py").read_text(encoding="utf-8")
        self.en = json.loads(Path("translations/en.json").read_text(encoding="utf-8"))
        self.zh = json.loads(Path("translations/zh-CN.json").read_text(encoding="utf-8"))

    def test_portrait_defaults_and_labels_exist(self):
        self.assertGreaterEqual(self.config["portrait_source_font_size"], 10)
        self.assertGreaterEqual(self.config["portrait_translation_font_size"], 10)
        for key in self.PORTRAIT_KEYS:
            self.assertIn(key, self.config)
            self.assertIn(key, self.sidebar)
        for label in self.REQUIRED_LABELS:
            self.assertIn(label, self.en)
            self.assertIn(label, self.zh)

    def test_all_portrait_keys_are_persisted_and_invalidate_preview(self):
        history_block = self.sidebar[
            self.sidebar.index("def _seed_config_history_once") :
            self.sidebar.index("def _render_diagnostics_tools")
        ]
        stamp_block = self.st_source[
            self.st_source.index("def _subtitle_preview_config_stamp") :
            self.st_source.index("def _generated_preview_path")
        ]
        for key in self.PORTRAIT_KEYS:
            self.assertIn(f'"{key}"', history_block)
            self.assertIn(f'"{key}"', stamp_block)


if __name__ == "__main__":
    unittest.main()
