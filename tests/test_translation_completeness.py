import unittest

from core.translate_lines import translation_may_omit_content


class TranslationCompletenessTest(unittest.TestCase):
    def test_flags_long_source_collapsed_to_short_idiom(self):
        self.assertTrue(
            translation_may_omit_content(
                "She'll develop this unconscious need to win my approval, and from then on, it's cake.",
                "小菜一碟",
            )
        )

    def test_accepts_compact_but_complete_translation(self):
        self.assertFalse(
            translation_may_omit_content(
                "Her name's not Lisa.",
                "她可不叫丽莎。",
            )
        )

    def test_flags_second_clause_only_translation_for_short_dialogue(self):
        self.assertTrue(
            translation_may_omit_content(
                "That's not me. It's not?",
                "不是吗？",
            )
        )

    def test_accepts_both_clauses_for_short_dialogue(self):
        self.assertFalse(
            translation_may_omit_content(
                "That's not me. It's not?",
                "那不是我。不是吗？",
            )
        )

    def test_flags_embedded_dialogue_question_translation_that_drops_question(self):
        self.assertTrue(
            translation_may_omit_content(
                "I can't say Where does he work?",
                "我不能说",
            )
        )

    def test_accepts_embedded_dialogue_question_translation_with_both_parts(self):
        self.assertFalse(
            translation_may_omit_content(
                "I can't say Where does he work?",
                "我不能说。他在哪儿工作？",
            )
        )

    def test_flags_leading_affirmative_answer_omission(self):
        self.assertTrue(
            translation_may_omit_content(
                "Yes, I did. Well, I'd say he's at work.",
                "他应该在上班",
            )
        )

    def test_accepts_leading_affirmative_answer_when_translated(self):
        self.assertFalse(
            translation_may_omit_content(
                "Yes, I did. Well, I'd say he's at work.",
                "是的，我去了。嗯，我觉得他应该在上班。",
            )
        )


if __name__ == "__main__":
    unittest.main()
