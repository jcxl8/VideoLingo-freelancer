import json
import unittest
from pathlib import Path
from unittest.mock import patch

from core import _7_sub_into_vid as subvid


ROOT = Path(__file__).resolve().parents[1]


class LandscapeWatermarkGuiTest(unittest.TestCase):
    def test_negative_100_is_the_15px_approved_default(self):
        self.assertEqual(subvid.LANDSCAPE_WATERMARK_DEFAULT_OFFSET, -100)
        self.assertEqual(subvid.landscape_watermark_effective_gap(-100), 15)
        self.assertEqual(subvid.landscape_watermark_effective_gap(-80), 35)
        self.assertEqual(subvid.landscape_watermark_effective_gap(-120), -5)

    def test_missing_config_falls_back_to_negative_100(self):
        with patch.object(subvid, "load_key", side_effect=KeyError):
            self.assertEqual(
                subvid._effective_watermark_offset(subvid.SUBTITLE_LAYOUT_LANDSCAPE),
                -100,
            )

    def test_sidebar_displays_calculated_gap_and_overlap_warning(self):
        source = (ROOT / "core/st_utils/sidebar_setting.py").read_text(encoding="utf-8")
        self.assertIn("landscape_watermark_effective_gap(l_wm_offset_val)", source)
        self.assertIn('t("Landscape watermark default gap")', source)
        self.assertIn('t("Current effective watermark gap")', source)
        self.assertIn('t("Watermark may overlap bilingual subtitles")', source)
        self.assertIn("LANDSCAPE_WATERMARK_DEFAULT_OFFSET", source)

    def test_gap_labels_are_localized(self):
        english = json.loads((ROOT / "translations/en.json").read_text(encoding="utf-8"))
        chinese = json.loads((ROOT / "translations/zh-CN.json").read_text(encoding="utf-8"))
        self.assertEqual(chinese["Landscape watermark default gap"], "横屏水印默认间距")
        self.assertEqual(chinese["Current effective watermark gap"], "当前有效水印间距")
        self.assertEqual(chinese["Watermark may overlap bilingual subtitles"], "水印可能与双语字幕重叠")
        self.assertEqual(english["Landscape watermark default gap"], "Landscape watermark default gap")


if __name__ == "__main__":
    unittest.main()
