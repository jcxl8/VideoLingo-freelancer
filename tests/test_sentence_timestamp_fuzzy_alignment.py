import unittest

import pandas as pd

from core._6_gen_sub import get_sentence_timestamps


class SentenceTimestampFuzzyAlignmentTest(unittest.TestCase):
    def test_allows_repeated_asr_word_in_sentence_alignment(self):
        words = [
            ("So", 1.0, 1.2),
            ("the", 1.2, 1.3),
            ("question", 1.3, 1.5),
            ("is,", 1.5, 1.7),
            ("is", 1.7, 1.9),
            ("how", 1.9, 2.0),
            ("can", 2.0, 2.1),
            ("we", 2.1, 2.2),
            ("coordinate", 2.2, 2.7),
            ("more,", 2.7, 3.0),
            ("you", 3.0, 3.1),
            ("know,", 3.1, 3.2),
            ("as", 3.2, 3.3),
            ("leading", 3.3, 3.5),
            ("players,", 3.5, 3.8),
            ("but", 3.8, 4.0),
            ("also", 4.0, 4.2),
            ("nation", 4.2, 4.5),
            ("states", 4.5, 4.7),
            ("even.", 4.7, 5.0),
        ]
        df_words = pd.DataFrame(words, columns=["text", "start", "end"])
        df_sentences = pd.DataFrame(
            {
                "Source": [
                    "So the question is how can we coordinate more, you know, as leading players, but also nation states even."
                ]
            }
        )

        result = get_sentence_timestamps(df_words, df_sentences)

        self.assertEqual(result[0]["start_word_idx"], 0)
        self.assertEqual(result[0]["end_word_idx"], 19)
        self.assertEqual(result[0]["speech_start"], 1.0)
        self.assertEqual(result[0]["speech_end"], 5.0)


if __name__ == "__main__":
    unittest.main()
