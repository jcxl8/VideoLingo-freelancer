import unittest

from core.asr_backend import audio_preprocess


class AsrAudioSegmentationTest(unittest.TestCase):
    def test_merges_short_final_remainder_into_previous_segment(self):
        segments = [
            (0.0, 34.063),
            (34.063, 66.299),
            (66.299, 67.14),
        ]

        result = audio_preprocess._merge_short_final_segment(segments, min_duration=3.0)

        self.assertEqual(result, [(0.0, 34.063), (34.063, 67.14)])

    def test_keeps_normal_final_segment_independent(self):
        segments = [(0.0, 30.0), (30.0, 34.0)]

        result = audio_preprocess._merge_short_final_segment(segments, min_duration=3.0)

        self.assertEqual(result, segments)

    def test_keeps_single_short_video_segment(self):
        segments = [(0.0, 1.5)]

        result = audio_preprocess._merge_short_final_segment(segments, min_duration=3.0)

        self.assertEqual(result, segments)


if __name__ == "__main__":
    unittest.main()
