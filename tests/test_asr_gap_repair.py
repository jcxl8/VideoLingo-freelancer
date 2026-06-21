import unittest
from unittest.mock import patch

import numpy as np

from core.asr_backend import whisperX_local


class AsrGapRepairTest(unittest.TestCase):
    def test_repairs_gap_slightly_longer_than_old_25_second_limit(self):
        combined_result = {
            "segments": [
                {
                    "text": "Bob Simon.",
                    "start": 1.4,
                    "end": 4.9,
                    "words": [{"word": "Simon.", "start": 4.619, "end": 4.9}],
                },
                {
                    "text": "I figured it out.",
                    "start": 30.658,
                    "end": 31.519,
                    "words": [{"word": "I", "start": 30.658, "end": 30.734}],
                },
            ]
        }
        raw_audio = np.zeros(int(40 * whisperX_local._WHISPERX_SR), dtype=np.float32)
        repaired_words = [
            {"word": "Magnus", "start": 4.401, "end": 4.72},
            {"word": "Carlsen", "start": 4.74, "end": 5.13},
            {"word": "is", "start": 5.21, "end": 5.29},
        ]

        with patch.object(whisperX_local, "_write_asr_gap_repair_report") as write_report:
            with patch.object(whisperX_local, "_transcribe_plain_segments", return_value={"segments": [{"text": "Magnus Carlsen is"}], "language": "en"}) as transcribe:
                with patch.object(
                    whisperX_local,
                    "_align_segments",
                    return_value={"segments": [{"text": "Magnus Carlsen is", "start": 4.4, "end": 5.3, "words": repaired_words}]},
                ):
                    result = whisperX_local._repair_transcription_gaps(
                        combined_result,
                        model=object(),
                        model_a=object(),
                        metadata={},
                        raw_audio=raw_audio,
                        vocal_audio=raw_audio,
                        device="cpu",
                        whisper_language="en",
                        detected_language="en",
                    )

        self.assertTrue(transcribe.called)
        self.assertEqual(len(result["segments"]), 3)
        self.assertEqual(result["segments"][-1]["text"], "Magnus Carlsen is")
        report_items = write_report.call_args.args[0]
        self.assertEqual(report_items[0]["status"], "inserted")
        self.assertAlmostEqual(report_items[0]["gap_seconds"], 25.758, places=3)


if __name__ == "__main__":
    unittest.main()
