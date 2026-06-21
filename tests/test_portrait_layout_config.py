import unittest
from unittest.mock import patch

from core import _7_sub_into_vid as subvid


class PortraitLayoutConfigTest(unittest.TestCase):
    def test_equal_default_source_and_translation_reference_sizes(self):
        with patch.object(subvid, "_safe_load_key", return_value=None):
            style = subvid._portrait_style_config()

        self.assertEqual(style.source_font_size, 45)
        self.assertEqual(style.translation_font_size, 45)
        self.assertEqual(style.hardsub_translation_font_size, 45)

    def test_portrait_sizes_scale_from_576_reference_width(self):
        self.assertEqual(subvid._scale_portrait_size(45, 576), 45)
        self.assertEqual(subvid._scale_portrait_size(45, 720), 56)
        self.assertEqual(subvid._scale_portrait_size(45, 1080), 84)

    def test_new_portrait_offset_precedes_legacy_value(self):
        values = {
            "portrait_bilingual_offset": 25,
            "bilingual_translation_offset": 90,
        }
        with patch.object(
            subvid,
            "_safe_load_key",
            side_effect=lambda key, default=None: values.get(key, default),
        ):
            result = subvid._portrait_int_setting(
                "portrait_bilingual_offset",
                "bilingual_translation_offset",
                0,
            )

        self.assertEqual(result, 25)


if __name__ == "__main__":
    unittest.main()
