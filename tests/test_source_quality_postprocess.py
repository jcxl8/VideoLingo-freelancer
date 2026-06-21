import unittest
from core.spacy_utils.source_quality import postprocess_source_segments
from core.spacy_utils.merge_short_segments import merge_lines

class SourceQualityPostprocessTest(unittest.TestCase):
    def test_splits_embedded_dialogue_question_after_short_answer(self):
        result, report = postprocess_source_segments(["I can't say Where does he work?"])
        self.assertEqual(result, ["I can't say.", "Where does he work?"])
        self.assertEqual(report[0]["type"], "embedded_question_split")

    def test_keeps_lowercase_indirect_question(self):
        result, report = postprocess_source_segments(["I can't say where he works."])
        self.assertEqual(result, ["I can't say where he works."])
        self.assertEqual(report, [])

    def test_removes_terminal_hanging_fragment(self):
        result, report = postprocess_source_segments(["We can't give out no information.", "I'm going to make a"])
        self.assertEqual(result, ["We can't give out no information."])
        self.assertEqual(report[0]["type"], "terminal_hanging_fragment_removed")

    def test_keeps_complete_final_sentence(self):
        result, report = postprocess_source_segments(["I'm going to make a call."])
        self.assertEqual(result, ["I'm going to make a call."])
        self.assertEqual(report, [])

    def test_short_segment_merge_keeps_capitalized_question_separate(self):
        result = merge_lines(["I can't say.", "Where does he work?"])
        self.assertEqual(result, ["I can't say.", "Where does he work?"])

if __name__ == "__main__":
    unittest.main()
