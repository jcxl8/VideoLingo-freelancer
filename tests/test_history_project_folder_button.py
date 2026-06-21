import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HistoryProjectFolderButtonTest(unittest.TestCase):
    def _manual_merge_block(self):
        source = (ROOT / "st.py").read_text(encoding="utf-8")
        start = source.index("def manual_subtitle_merge_section():")
        end = source.index("\ndef process_text(", start)
        return source, source[start:end]

    def test_history_project_selection_renders_open_folder_action(self):
        _, block = self._manual_merge_block()

        project_selector = block.index('t("Select history project")')
        open_button = block.index('t("Open Project Folder")')
        video_selector = block.index('t("Select history video file")')
        self.assertLess(project_selector, open_button)
        self.assertLess(open_button, video_selector)
        self.assertIn(
            '_open_archived_dir(os.path.abspath(selected_project))',
            block,
        )
        self.assertIn('st.error(t("Project folder not found"))', block)

    def test_history_merge_output_is_stored_in_selected_project(self):
        source, block = self._manual_merge_block()
        helper_start = source.index("def _manual_output_video_path(")
        helper_end = source.index("\ndef _render_ambiguity_report(", helper_start)
        helpers = source[helper_start:helper_end]

        self.assertIn("output_dir=None", helpers)
        self.assertIn("target_dir = output_dir or MANUAL_MERGE_DIR", helpers)
        self.assertIn("manual_output_dir = (", block)
        self.assertIn(
            "os.path.abspath(selected_project) if using_history_video",
            block,
        )
        self.assertGreaterEqual(block.count("output_dir=manual_output_dir"), 2)

    def test_history_result_area_offers_project_folder_button(self):
        _, block = self._manual_merge_block()
        download = block.index('t("Download Merged Video")')
        result_open = block.index('key="open_manual_result_project_folder"')
        self.assertLess(download, result_open)
        self.assertIn(
            '_open_archived_dir(os.path.abspath(selected_project))',
            block[result_open:],
        )

    def test_open_folder_labels_are_localized(self):
        english = json.loads((ROOT / "translations/en.json").read_text(encoding="utf-8"))
        chinese = json.loads((ROOT / "translations/zh-CN.json").read_text(encoding="utf-8"))
        self.assertEqual(english["Open Project Folder"], "Open Project Folder")
        self.assertEqual(english["Project folder not found"], "Project folder not found")
        self.assertEqual(chinese["Open Project Folder"], "打开项目所在文件夹")
        self.assertEqual(chinese["Project folder not found"], "未找到项目文件夹")


if __name__ == "__main__":
    unittest.main()
