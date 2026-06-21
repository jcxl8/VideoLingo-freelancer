import unittest

import pandas as pd

from core.spacy_utils.merge_short_segments import merge_lines


class PauseAwareSegmentMergeTest(unittest.TestCase):
    def test_does_not_merge_short_complete_sentence_across_long_pause(self):
        words = pd.DataFrame(
            [
                {"text": "Hey,", "start": 0.92, "end": 1.28},
                {"text": "Lisa.", "start": 1.28, "end": 1.64},
                {"text": "Her", "start": 5.00, "end": 5.36},
                {"text": "name's", "start": 5.36, "end": 5.68},
                {"text": "not", "start": 5.68, "end": 5.82},
                {"text": "Lisa.", "start": 5.82, "end": 6.12},
            ]
        )

        result = merge_lines(
            ["Hey, Lisa.", "Her name's not Lisa."],
            timed_words=words,
        )

        self.assertEqual(result, ["Hey, Lisa.", "Her name's not Lisa."])

    def test_still_merges_short_complete_sentence_when_speech_is_contiguous(self):
        words = pd.DataFrame(
            [
                {"text": "Absolutely.", "start": 1.00, "end": 1.45},
                {"text": "They're", "start": 1.60, "end": 1.90},
                {"text": "going", "start": 1.90, "end": 2.10},
                {"text": "again.", "start": 2.10, "end": 2.45},
            ]
        )

        result = merge_lines(
            ["Absolutely.", "They're going again."],
            timed_words=words,
        )

        self.assertEqual(result, ["Absolutely. They're going again."])


if __name__ == "__main__":
    unittest.main()
