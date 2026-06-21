import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from core import _7_sub_into_vid as subvid
from core.subtitle_formats import read_srt_entries


class AnalysisCacheTest(unittest.TestCase):
    def test_srt_cache_returns_fresh_values_and_invalidates_on_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.srt"
            path.write_text("1\n00:00:00,000 --> 00:00:01,000\nFirst\n", encoding="utf-8")
            first = read_srt_entries(path)
            first[0]["text"] = "mutated"
            self.assertEqual(read_srt_entries(path)[0]["text"], "First")

            path.write_text("1\n00:00:00,000 --> 00:00:01,000\nSecond line\n", encoding="utf-8")
            os.utime(path, None)
            self.assertEqual(read_srt_entries(path)[0]["text"], "Second line")

    def test_hardsub_detection_reuses_video_fingerprint_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "source.mp4"
            video.write_bytes(b"video")
            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            box = {"top": 70, "bottom": 80, "left": 20, "right": 80, "score": 1, "lines": 1}
            subvid.clear_hardsub_detection_cache()
            with patch.object(subvid, "_sample_video_frames", return_value=[frame] * 4) as sampler:
                with patch.object(subvid, "_detect_hardsub_box_in_frame", return_value=box):
                    first = subvid.detect_existing_source_hardsub(str(video), 100, 100)
                    second = subvid.detect_existing_source_hardsub(str(video), 100, 100)
            self.assertEqual(first, second)
            self.assertEqual(sampler.call_count, 1)


if __name__ == "__main__":
    unittest.main()
