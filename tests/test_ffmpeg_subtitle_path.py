import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import _7_sub_into_vid as subvid


class FfmpegSubtitlePathTest(unittest.TestCase):
    def test_single_subtitle_filter_stages_unsafe_history_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unsafe_dir = root / "today's AI ｜ archive"
            unsafe_dir.mkdir()
            subtitle = unsafe_dir / "translated subtitle.srt"
            subtitle.write_text(
                "1\n00:00:00,000 --> 00:00:02,000\n测试字幕\n",
                encoding="utf-8",
            )

            with patch.object(subvid, "OUTPUT_DIR", str(root / "output")):
                filter_text = subvid._subtitle_filter(
                    str(subtitle),
                    48,
                    "Arial Unicode MS",
                    "&H00FFFF",
                    "&H000000",
                    1,
                )

            self.assertNotIn("today's AI", filter_text)
            staged_value = filter_text.split("subtitles=", 1)[1].split(":force_style", 1)[0]
            staged_path = Path(staged_value)
            self.assertTrue(staged_path.is_file())
            self.assertEqual(staged_path.read_text(encoding="utf-8"), subtitle.read_text(encoding="utf-8"))
            self.assertNotIn("'", os.path.basename(staged_value))
            self.assertNotIn(" ", os.path.basename(staged_value))


if __name__ == "__main__":
    unittest.main()
