import os
import tempfile
import time
import unittest
from pathlib import Path

from core.st_utils.manual_merge_files import write_bytes_if_changed


ROOT = Path(__file__).resolve().parents[1]


class ManualPreviewRerunTest(unittest.TestCase):
    def test_unchanged_file_keeps_mtime_for_preview_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manual_history_src.srt"
            self.assertTrue(write_bytes_if_changed(path, b"subtitle"))
            first_mtime = path.stat().st_mtime_ns
            time.sleep(0.002)

            self.assertFalse(write_bytes_if_changed(path, b"subtitle"))

            self.assertEqual(path.stat().st_mtime_ns, first_mtime)
            self.assertTrue(write_bytes_if_changed(path, b"changed subtitle"))
            self.assertNotEqual(path.stat().st_mtime_ns, first_mtime)

    def test_manual_writers_are_content_stable(self):
        source = (ROOT / "st.py").read_text(encoding="utf-8")
        upload_block = source[source.index("def _save_uploaded_file"):source.index("def _allowed_video_exts")]
        split_block = source[source.index("def _split_bilingual_srt"):source.index("def _parse_srt_file")]
        self.assertIn("write_bytes_if_changed", upload_block)
        self.assertIn("write_bytes_if_changed", split_block)

    def test_cleanup_is_consumed_before_preview_rendering(self):
        source = (ROOT / "st.py").read_text(encoding="utf-8")
        block = source[source.index("def manual_subtitle_merge_section"):source.index("def text_processing_section")]
        self.assertLess(block.index("_consume_manual_merge_cleanup_request()"), block.index("_render_subtitle_preview("))
        self.assertIn("on_click=_request_manual_merge_cleanup", block)
        self.assertIn('"manual_video_upload",', source)
        self.assertIn("st.session_state.pop(key, None)", source)


if __name__ == "__main__":
    unittest.main()
