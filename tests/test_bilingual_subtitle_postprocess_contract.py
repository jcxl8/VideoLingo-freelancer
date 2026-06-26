from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BilingualSubtitlePostprocessContractTest(unittest.TestCase):
    def test_keeps_orphan_short_words_with_following_lowercase_fragment(self):
        source = (ROOT / "core" / "_6_gen_sub.py").read_text(encoding="utf-8")

        self.assertIn("short orphan words at entry boundaries", source)
        self.assertIn('len(en_words_i[-1]) <= 3', source)
        self.assertIn('en_next_new = (orphan + " " + en_next).strip()', source)

    def test_keeps_multi_word_proper_nouns_together_when_resplitting(self):
        source = (ROOT / "core" / "_6_gen_sub.py").read_text(encoding="utf-8")

        self.assertIn("Avoid breaking multi-word proper nouns across entries", source)
        self.assertIn("proper_start = split_at - 1", source)
        self.assertIn("split_at = proper_start", source)


if __name__ == "__main__":
    unittest.main()
