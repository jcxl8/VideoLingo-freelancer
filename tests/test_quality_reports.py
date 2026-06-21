import json
import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from core._3_2_split_meaning import write_segmentation_quality_report
from core.asr_backend.audio_preprocess import _write_asr_quality_report


class QualityReportsTest(unittest.TestCase):
    def test_asr_quality_report_flags_long_gap_and_duplicate_word(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, "asr.json")
            report_md = os.path.join(tmpdir, "asr.md")
            df = pd.DataFrame(
                [
                    {"text": "hello", "start": 0.0, "end": 0.2},
                    {"text": "the", "start": 5.0, "end": 5.2},
                    {"text": "the", "start": 5.25, "end": 5.4},
                ]
            )
            with patch("core.asr_backend.audio_preprocess._2_ASR_QUALITY_REPORT", report_path), \
                 patch("core.asr_backend.audio_preprocess._2_ASR_QUALITY_REPORT_MD", report_md):
                report = _write_asr_quality_report(df)

            self.assertEqual(report["summary"]["long_gap_count"], 1)
            self.assertEqual(report["summary"]["repeated_word_count"], 1)
            self.assertTrue(os.path.exists(report_path))

    def test_segmentation_report_flags_short_and_continuation_segments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, "seg.json")
            report_md = os.path.join(tmpdir, "seg.md")
            with patch("core._3_2_split_meaning._3_2_SEGMENTATION_REPORT", report_path), \
                 patch("core._3_2_split_meaning._3_2_SEGMENTATION_REPORT_MD", report_md), \
                 patch("core._3_2_split_meaning.load_key", side_effect=lambda key: 10 if key == "min_split_source_words" else 20):
                items = write_segmentation_quality_report(["and then", "This is a complete enough sentence for checking."])

            self.assertTrue(any(item["type"] == "short_segment" for item in items))
            self.assertTrue(any(item["type"] == "continuation_start" for item in items))
            with open(report_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["summary"]["item_count"], len(items))


if __name__ == "__main__":
    unittest.main()
