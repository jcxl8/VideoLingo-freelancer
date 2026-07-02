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

    def test_accepts_short_complete_acknowledgement_pairs(self):
        examples = [
            ("Yeah. All right.", "是的。好的。"),
            ("All right. Cool.", "好的。不错。"),
            ("We should go? Okay.", "我们该走了吗？好的。"),
            ("Okay.. No worries.", "好 没事儿"),
            ("Sure. All right.", "对 行"),
        ]
        for source, translation in examples:
            with self.subTest(source=source):
                self.assertFalse(translation_may_omit_content(source, translation))

    def test_flags_leading_self_intro_omission(self):
        self.assertTrue(
            translation_may_omit_content(
                "I'm Bob Simon. It didn't go perfectly though.",
                "不过录得不太顺利",
            )
        )

    def test_accepts_leading_self_intro_when_translated(self):
        self.assertFalse(
            translation_may_omit_content(
                "I'm Bob Simon. It didn't go perfectly though.",
                "我是鲍勃·西蒙，不过录得不太顺利。",
            )
        )

    def test_flags_repeated_self_intro_omission(self):
        self.assertTrue(
            translation_may_omit_content(
                "I'm Eminem. I'm Slim Shady.",
                "我是斯利姆·沙迪",
            )
        )

    def test_accepts_repeated_self_intro_when_translated(self):
        self.assertFalse(
            translation_may_omit_content(
                "I'm Eminem. I'm Slim Shady.",
                "我是 Eminem，也是斯利姆·沙迪。",
            )
        )

    def test_flags_repeated_self_intro_with_comma_suffix_omission(self):
        self.assertTrue(
            translation_may_omit_content(
                "I'm Bob Simon. I'm Anderson Cooper, you know?",
                "我是安德森·库珀，你懂吧？",
            )
        )

    def test_accepts_repeated_self_intro_with_comma_suffix_when_translated(self):
        self.assertFalse(
            translation_may_omit_content(
                "I'm Bob Simon. I'm Anderson Cooper, you know?",
                "我是鲍勃·西蒙，我是安德森·库珀，你懂吧？",
            )
        )

    def test_flags_leading_you_know_question_omission(self):
        self.assertTrue(
            translation_may_omit_content(
                "You know? It is a little the first time you do it for 60 minutes.",
                "第一次录《60 分钟》时",
            )
        )

    def test_accepts_leading_you_know_question_when_translated(self):
        self.assertFalse(
            translation_may_omit_content(
                "You know? It is a little the first time you do it for 60 minutes.",
                "你懂吧？第一次录《60 分钟》时会有点这种感觉。",
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
