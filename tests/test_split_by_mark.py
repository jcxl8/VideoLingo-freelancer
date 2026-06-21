import unittest

from core.spacy_utils.split_by_mark import _split_on_sentence_end


class SplitByMarkTest(unittest.TestCase):
    def test_keeps_leading_initial_with_full_person_name(self):
        text = (
            "The latest milestone occurred this summer when the microbiologist "
            "J. Craig Venter announced the result."
        )

        self.assertEqual(_split_on_sentence_end(text), text)

    def test_keeps_middle_initial_with_person_name(self):
        text = "George W. Bush announced the result."

        self.assertEqual(_split_on_sentence_end(text), text)

    def test_keeps_multiple_initials_with_person_name(self):
        text = "The author J. K. Rowling attended."

        self.assertEqual(_split_on_sentence_end(text), text)

    def test_still_splits_two_complete_sentences(self):
        text = "The experiment ended. Another experiment began."

        self.assertEqual(
            _split_on_sentence_end(text),
            "The experiment ended.\nAnother experiment began.",
        )


if __name__ == "__main__":
    unittest.main()
