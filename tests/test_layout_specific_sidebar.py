import unittest
from pathlib import Path

from core.st_utils.sidebar_setting import _subtitle_layout_settings_visibility


ROOT = Path(__file__).resolve().parents[1]


class LayoutSpecificSidebarTest(unittest.TestCase):
    def test_only_selected_layout_section_is_visible(self):
        self.assertEqual(_subtitle_layout_settings_visibility("portrait_9_16"), (True, False))
        self.assertEqual(_subtitle_layout_settings_visibility("landscape"), (False, True))
        self.assertEqual(_subtitle_layout_settings_visibility("auto"), (False, False))

    def test_page_uses_visibility_flags_for_both_sections(self):
        source = (ROOT / "core/st_utils/sidebar_setting.py").read_text(encoding="utf-8")
        self.assertIn("show_portrait_settings, show_landscape_settings =", source)
        self.assertIn("if show_portrait_settings:", source)
        self.assertIn("if show_landscape_settings:", source)


if __name__ == "__main__":
    unittest.main()
