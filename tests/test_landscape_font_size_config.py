import json
import unittest
from pathlib import Path
from unittest.mock import patch

from core import _7_sub_into_vid as subvid


ROOT = Path(__file__).resolve().parents[1]


class LandscapeFontSizeConfigTest(unittest.TestCase):
    def test_reference_font_sizes_scale_with_video_height(self):
        values = {
            "landscape_source_font_size": 52,
            "landscape_translation_font_size": 60,
        }
        with patch.object(subvid, "load_key", side_effect=lambda key: values[key]):
            self.assertEqual(subvid._landscape_font_sizes(1920, 1080), (52, 60))
            self.assertEqual(subvid._landscape_font_sizes(3840, 2160), (104, 120))

    def test_config_and_gui_expose_both_landscape_font_sizes(self):
        config = (ROOT / "config.yaml").read_text(encoding="utf-8")
        sidebar = (ROOT / "core/st_utils/sidebar_setting.py").read_text(encoding="utf-8")
        preview = (ROOT / "st.py").read_text(encoding="utf-8")

        self.assertIn("landscape_source_font_size:", config)
        self.assertIn("landscape_translation_font_size:", config)
        for key in ("landscape_source_font_size", "landscape_translation_font_size"):
            self.assertIn(key, sidebar)
            self.assertIn(key, preview)

    def test_font_size_labels_are_localized(self):
        english = json.loads((ROOT / "translations/en.json").read_text(encoding="utf-8"))
        chinese = json.loads((ROOT / "translations/zh-CN.json").read_text(encoding="utf-8"))

        self.assertEqual(english["Landscape Source Font Size"], "Landscape Source Font Size")
        self.assertEqual(chinese["Landscape Source Font Size"], "横屏原文字号")
        self.assertEqual(chinese["Landscape Translation Font Size"], "横屏译文字号")


if __name__ == "__main__":
    unittest.main()
