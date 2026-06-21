import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ArchiveWithoutPreviewTest(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "st.py").read_text(encoding="utf-8")

    def test_archive_request_is_handled_before_generated_preview(self):
        section = self.source[
            self.source.index("def text_processing_section():") :
            self.source.index("\ndef process_text(", self.source.index("def text_processing_section():"))
        ]

        archive_guard = section.index("_text_archive_requested()")
        first_generated_preview = section.index("_render_generated_merge_choice()")
        self.assertLess(archive_guard, first_generated_preview)

    def test_archive_helper_does_not_render_preview(self):
        helper = self.source[
            self.source.index("def _archive_text_outputs_to_history():") :
            self.source.index("\ndef _render_open_output_button", self.source.index("def _archive_text_outputs_to_history():"))
        ]

        self.assertIn('st.session_state["last_text_archive_dir"] = cleanup()', helper)
        self.assertIn("st.rerun()", helper)
        self.assertNotIn("preview", helper.lower())

    def test_archive_buttons_use_shared_helper(self):
        self.assertGreaterEqual(self.source.count("_archive_text_outputs_to_history()"), 3)
        self.assertNotIn('st.session_state["last_text_archive_dir"] = cleanup()\n                st.rerun()', self.source)
        self.assertNotIn('st.session_state["last_text_archive_dir"] = cleanup()\n        st.rerun()', self.source)


if __name__ == "__main__":
    unittest.main()
