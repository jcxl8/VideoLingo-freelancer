import unittest
from unittest.mock import patch

from core.translate_lines import (
    _extract_glossary_terms,
    _finalize_translations_after_refine,
    _normalize_proper_name_translations,
    translation_may_omit_content,
)


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

    def test_keeps_complete_translator_output_when_refine_omits_content(self):
        source = "I'm Bob Simon. It didn't go perfectly though."
        raw = "我是鲍勃·西蒙。不过事情并没有完美地进展。"
        refined = "不过录得不太顺利"

        with patch("core.translate_lines.console.print"):
            self.assertEqual(
                _finalize_translations_after_refine([source], [refined], [raw], "zh-CN", []),
                [raw],
            )

    def test_keeps_translator_output_when_refine_collapses_to_quote(self):
        source = "It's like, I'm Anderson Cooper."
        raw = "就像，我是安德森·库珀。"
        refined = "’"

        with patch("core.translate_lines.console.print"):
            self.assertEqual(
                _finalize_translations_after_refine([source], [refined], [raw], "zh-CN", []),
                [raw],
            )

    def test_normalizes_refined_english_name_to_existing_chinese_translation(self):
        source_lines = [
            "I'm? Anderson Cooper. I'm Anderson Cooper.",
            "I'm Bob Simon. I'm Anderson Cooper, you know?",
        ]
        raw = [
            "我是？安德森·库珀。我是安德森·库珀。",
            "我是鲍勃·西蒙。我是安德森·库珀，你知道的吧？",
        ]
        refined = [
            "我是…… Anderson Cooper？我是 Anderson Cooper",
            "我是鲍勃·西蒙。我是 Anderson Cooper，对吧？",
        ]

        self.assertEqual(
            _normalize_proper_name_translations(source_lines, refined, raw),
            [
                "我是……安德森·库珀？我是安德森·库珀",
                "我是鲍勃·西蒙。我是安德森·库珀，对吧？",
            ],
        )

    def test_skips_identity_multi_word_name_glossary_terms(self):
        prompt = '"Anderson Cooper": "Anderson Cooper"\n"Bob Simon": "鲍勃·西蒙"'

        self.assertEqual(_extract_glossary_terms(prompt), [("Bob Simon", "鲍勃·西蒙")])

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

    def test_flags_omitted_repetition_count(self):
        self.assertTrue(
            translation_may_omit_content(
                "like ten I'ms for each one that actually gets on the air.",
                "每条真正播出的 I'm 介绍",
            )
        )

    def test_accepts_translated_repetition_count(self):
        self.assertFalse(
            translation_may_omit_content(
                "like ten I'ms for each one that actually gets on the air.",
                "每条真正播出的 I'm 介绍大概要录十次",
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
