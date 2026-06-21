import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import _7_sub_into_vid as subvid


def _write_srt(path, text):
    Path(path).write_text(
        f"1\n00:00:01,000 --> 00:00:03,000\n{text}\n",
        encoding="utf-8",
    )


class LandscapeSingleAssTest(unittest.TestCase):
    def test_style_version_invalidates_oversized_cached_previews(self):
        self.assertGreaterEqual(subvid.SUBTITLE_STYLE_VERSION, 19)

    def test_landscape_single_modes_use_target_resolution_ass(self):
        with tempfile.TemporaryDirectory() as directory:
            src = os.path.join(directory, "src.srt")
            trans = os.path.join(directory, "trans.srt")
            _write_srt(src, "Source subtitle")
            _write_srt(trans, "译文字幕")
            values = {
                "landscape_source_font_size": 50,
                "landscape_translation_font_size": 55,
            }
            with patch.object(subvid, "OUTPUT_DIR", directory), patch.object(
                subvid, "load_key", side_effect=lambda key: values.get(key, 0)
            ):
                translation_filter = subvid._subtitle_filters_for_mode(
                    None,
                    trans,
                    "translation_only",
                    1920,
                    1080,
                    subvid.SUBTITLE_LAYOUT_LANDSCAPE,
                )[0]
                source_filter = subvid._subtitle_filters_for_mode(
                    src,
                    None,
                    "source_only",
                    1920,
                    1080,
                    subvid.SUBTITLE_LAYOUT_LANDSCAPE,
                )[0]

            self.assertIn("landscape_single_", translation_filter)
            self.assertIn("landscape_single_", source_filter)
            for filter_text, expected_size in ((translation_filter, 55), (source_filter, 50)):
                ass_path = filter_text.split("subtitles=", 1)[1]
                ass_text = Path(ass_path).read_text(encoding="utf-8")
                self.assertIn("PlayResX: 1920", ass_text)
                self.assertIn("PlayResY: 1080", ass_text)
                self.assertIn(f",{expected_size},", ass_text)
                self.assertIn("Dialogue: 0,", ass_text)


if __name__ == "__main__":
    unittest.main()
