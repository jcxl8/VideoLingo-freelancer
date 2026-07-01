import unittest
import tempfile
from pathlib import Path

import pandas as pd

from core._6_gen_sub import (
    align_timestamp,
    _drop_likely_standalone_ack_hallucinations,
    _merge_short_adjacent_subtitles,
    _repair_adjacent_source_phrase_splits,
    _split_long_display_subtitles,
)


class LongSubtitleTimelineSplitTest(unittest.TestCase):
    def test_landscape_comfortable_cps_does_not_split_on_chinese_spaces(self):
        df = pd.DataFrame([
            {
                "Source": (
                    "Twitter is a war zone. If somebody's going to jump in the war zone, "
                    "it's like, okay you're in the arena."
                ),
                "Translation": "推特就是个战场。如果有人要跳进去 这个战区，那就来吧，你已身处角斗场",
                "display_timestamp": (14.940, 20.180),
                "speech_timestamp": (14.940, 19.800),
            }
        ])

        result = _split_long_display_subtitles(
            df,
            target_width=1920,
            target_height=1080,
        )

        self.assertEqual(len(result), 1)
        self.assertIn("war zone", result.iloc[0]["Source"])
        self.assertEqual(result.iloc[0]["Translation"], df.iloc[0]["Translation"])

    def test_source_sentence_boundaries_split_matching_translation_parts(self):
        df = pd.DataFrame([
            {
                "Source": "Oh my god, how did you do that? it's easier than it looks.",
                "Translation": "天哪 你怎么做到的？其实很容易的",
                "display_timestamp": (1.16, 12.72),
                "speech_timestamp": (1.16, 8.72),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=576, target_height=1024)

        self.assertEqual(len(result), 3)
        self.assertEqual(
            result["Source"].tolist(),
            ["Oh my god,", "how did you do that?", "it's easier than it looks."],
        )
        self.assertEqual(
            result["Translation"].tolist(),
            ["天哪", "你怎么做到的？", "其实很容易的"],
        )
        self.assertEqual(result.iloc[0]["display_timestamp"][0], 1.16)
        self.assertEqual(result.iloc[-1]["display_timestamp"][1], 12.72)
        self.assertEqual(result.iloc[0]["display_timestamp"][1], result.iloc[1]["display_timestamp"][0])
        self.assertEqual(result.iloc[1]["display_timestamp"][1], result.iloc[2]["display_timestamp"][0])

    def test_long_silence_does_not_extend_already_readable_subtitle(self):
        df_words = pd.DataFrame(
            [
                ("Oh", 1.16, 1.68),
                ("my", 1.68, 2.20),
                ("god,", 2.20, 2.82),
                ("how", 3.14, 4.32),
                ("did", 4.32, 4.54),
                ("you", 4.54, 4.66),
                ("do", 4.66, 4.94),
                ("that?", 4.94, 5.22),
                ("it's", 6.22, 7.38),
                ("easier", 7.38, 8.08),
                ("than", 8.08, 8.30),
                ("it", 8.30, 8.40),
                ("looks.", 8.40, 8.72),
                ("No,", 13.66, 14.18),
                ("I", 14.44, 14.68),
                ("don't", 14.68, 14.90),
                ("think", 14.90, 15.02),
                ("so.", 15.02, 15.18),
            ],
            columns=["text", "start", "end"],
        )
        df_translate = pd.DataFrame([
            {
                "Source": "Oh my god, how did you do that? it's easier than it looks.",
                "Translation": "天哪，你怎么做到的？其实很容易的",
            },
            {"Source": "No, I don't think so.", "Translation": "不，我不觉得"},
        ])

        with tempfile.TemporaryDirectory() as directory:
            align_timestamp(
                df_words,
                df_translate,
                [("src.srt", ["Source"])],
                directory,
            )

            exported = (Path(directory) / "src.srt").read_text(encoding="utf-8")

        self.assertIn("00:00:01,160 --> 00:00:08,970", exported)
        self.assertNotIn("00:00:01,160 --> 00:00:12,720", exported)

    def test_long_translation_is_split_into_multiple_timed_rows(self):
        df = pd.DataFrame([
            {
                "Source": (
                    "IRS code allows us to deduct from your taxable income a percentage "
                    "of your workspace relative to your overall home."
                ),
                "Translation": "根据《国内税收法典》，您可从应税收入中扣除 工作空间占房屋面积比例对应的费用",
                "display_timestamp": (34.10, 39.88),
                "speech_timestamp": (34.10, 39.88),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=576, target_height=1024)

        self.assertEqual(len(result), 3)
        self.assertEqual(
            result["Translation"].tolist(),
            ["根据《国内税收法典》", "您可从应税收入中扣除", "工作空间占房屋面积比例对应的费用"],
        )
        self.assertEqual(result.iloc[0]["display_timestamp"][0], 34.10)
        self.assertEqual(result.iloc[-1]["display_timestamp"][1], 39.88)
        self.assertEqual(result.iloc[0]["display_timestamp"][1], result.iloc[1]["display_timestamp"][0])
        self.assertEqual(result.iloc[1]["display_timestamp"][1], result.iloc[2]["display_timestamp"][0])

    def test_visual_wrapping_does_not_create_timed_srt_fragments(self):
        df = pd.DataFrame([
            {
                "Source": "The last minute of 60 minutes is sponsored by UnitedHealthcare.",
                "Translation": "《60 分钟》的最后时刻由 UnitedHealthcare 赞助",
                "display_timestamp": (1.80, 6.93),
                "speech_timestamp": (1.80, 6.93),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=576, target_height=1024)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["Source"], "The last minute of 60 minutes is sponsored by UnitedHealthcare.")
        self.assertEqual(result.iloc[0]["Translation"], "《60 分钟》的最后时刻由 UnitedHealthcare 赞助")

    def test_latin_abbreviation_spaces_do_not_create_timed_srt_fragments(self):
        df = pd.DataFrame([
            {
                "Source": "And everyone knows that AI is not that funny.",
                "Translation": "而且大家都知道 AI 没那么搞笑",
                "display_timestamp": (61.36, 64.44),
                "speech_timestamp": (61.36, 64.44),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=576, target_height=1024)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["Source"], "And everyone knows that AI is not that funny.")
        self.assertEqual(result.iloc[0]["Translation"], "而且大家都知道 AI 没那么搞笑")

    def test_dependent_prepositional_phrase_merges_with_previous_clause(self):
        merged = _merge_short_adjacent_subtitles(pd.DataFrame([
            {
                "Source": "When Nolan was 16 he saw an IMAX documentary",
                "Translation": "诺兰 16 岁时看了一部 IMAX 纪录片",
                "speech_timestamp": (13.020, 16.940),
            },
            {
                "Source": "at a museum and was spellbound by the five -story screen.",
                "Translation": "在博物馆 便对那五层楼高的银幕着了迷",
                "speech_timestamp": (16.940, 21.910),
            },
        ]))

        self.assertEqual(len(merged), 1)
        self.assertEqual(
            merged.iloc[0]["Source"],
            "When Nolan was 16 he saw an IMAX documentary at a museum and was spellbound by the five -story screen.",
        )
        self.assertEqual(
            merged.iloc[0]["Translation"],
            "诺兰 16 岁时看了一部 IMAX 纪录片 在博物馆 便对那五层楼高的银幕着了迷",
        )

    def test_short_answer_with_overfull_translation_merges_following_context(self):
        merged = _merge_short_adjacent_subtitles(pd.DataFrame([
            {
                "Source": "Probably was.",
                "Translation": "很可能就是 我们亲眼目睹《奥德赛》被剪辑拼接",
                "speech_timestamp": (39.700, 44.860),
            },
            {
                "Source": "We watch the Odyssey being cut and glued together in the last film lab of its kind in the world.",
                "Translation": "在世界上最后一个这样的胶片实验室里",
                "speech_timestamp": (44.860, 49.130),
            },
        ]))

        self.assertEqual(len(merged), 1)
        self.assertEqual(
            merged.iloc[0]["Source"],
            "Probably was. We watch the Odyssey being cut and glued together in the last film lab of its kind in the world.",
        )
        self.assertEqual(
            merged.iloc[0]["Translation"],
            "很可能就是 我们亲眼目睹《奥德赛》被剪辑拼接 在世界上最后一个这样的胶片实验室里",
        )

    def test_tiny_source_fragment_merges_into_complete_phrase(self):
        merged = _merge_short_adjacent_subtitles(pd.DataFrame([
            {
                "Source": "There it",
                "Translation": "出来了",
                "speech_timestamp": (63.579, 64.204),
            },
            {
                "Source": "is.",
                "Translation": "哦",
                "speech_timestamp": (64.204, 64.651),
            },
        ]))

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged.iloc[0]["Source"], "There it is.")
        self.assertEqual(merged.iloc[0]["Translation"], "出来了")

    def test_chained_lowercase_continuations_merge_until_clause_completes(self):
        merged = _merge_short_adjacent_subtitles(pd.DataFrame([
            {
                "Source": "Digital photography and",
                "Translation": "数字摄影和剪辑更快",
                "speech_timestamp": (26.320, 28.313),
            },
            {
                "Source": "editing are faster and",
                "Translation": "更便宜",
                "speech_timestamp": (28.313, 30.116),
            },
            {
                "Source": "cheaper so almost",
                "Translation": "所以几乎",
                "speech_timestamp": (30.116, 31.540),
            },
            {
                "Source": "no one does this in the world anymore. Look at the slicing machine.",
                "Translation": "现在没人再这么干了 瞧瞧这台胶片切片机",
                "speech_timestamp": (31.540, 36.530),
            },
        ]))

        self.assertEqual(len(merged), 1)
        self.assertEqual(
            merged.iloc[0]["Source"],
            "Digital photography and editing are faster and cheaper so almost no one does this in the world anymore. Look at the slicing machine.",
        )

    def test_short_isolated_thank_you_can_be_dropped_as_likely_asr_hallucination(self):
        filtered = _drop_likely_standalone_ack_hallucinations(pd.DataFrame([
            {
                "Source": "There it is.",
                "Translation": "出来了",
                "speech_timestamp": (63.579, 64.651),
            },
            {
                "Source": "Thank you.",
                "Translation": "谢谢",
                "speech_timestamp": (66.299, 66.924),
            },
            {
                "Source": "That is very clean.",
                "Translation": "非常干净",
                "speech_timestamp": (67.000, 69.000),
            },
        ]))

        self.assertEqual(filtered["Source"].tolist(), ["There it is.", "That is very clean."])

    def test_short_translation_is_not_split(self):
        df = pd.DataFrame([
            {
                "Source": "Hey, Lisa!",
                "Translation": "她可不叫丽莎",
                "display_timestamp": (1.0, 2.0),
                "speech_timestamp": (1.0, 2.0),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=576, target_height=1024)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["Translation"], "她可不叫丽莎")

    def test_discourse_marker_line_is_split_into_next_timed_subtitle(self):
        df = pd.DataFrame([
            {
                "Source": "I mean, Emily came up with clicks and whistles at first.",
                "Translation": "其实 咔嗒声和哨音最初是艾米莉想出来的",
                "display_timestamp": (53.24, 57.74),
                "speech_timestamp": (53.24, 57.74),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=576, target_height=1024)

        self.assertEqual(len(result), 2)
        self.assertEqual(
            result["Translation"].tolist(),
            ["其实", "咔嗒声和哨音最初是艾米莉想出来的"],
        )
        self.assertEqual(result.iloc[0]["display_timestamp"][0], 53.24)
        self.assertEqual(result.iloc[-1]["display_timestamp"][1], 57.74)
        self.assertEqual(result.iloc[0]["display_timestamp"][1], result.iloc[1]["display_timestamp"][0])

    def test_discourse_marker_without_following_clause_is_not_split(self):
        df = pd.DataFrame([
            {
                "Source": "Actually.",
                "Translation": "其实",
                "display_timestamp": (1.0, 1.8),
                "speech_timestamp": (1.0, 1.8),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=576, target_height=1024)

        self.assertEqual(len(result), 1)

    def test_enumerated_teacher_subtitle_splits_without_breaking_person_name(self):
        df = pd.DataFrame([
            {
                "Source": (
                    "But I had an amazing Russian teacher, an amazing Korean teacher, "
                    "and an amazing alien language teacher in Steven Spielberg,"
                ),
                "Translation": "但我有超棒的俄语老师、超棒的韩语老师 还有史蒂文·斯皮尔伯格当我的外星语言老师",
                "display_timestamp": (15.50, 22.58),
                "speech_timestamp": (15.50, 22.58),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=1920, target_height=3414)

        self.assertEqual(len(result), 3)
        self.assertEqual(
            result["Translation"].tolist(),
            ["但我有超棒的俄语老师", "超棒的韩语老师", "还有史蒂文·斯皮尔伯格当我的外星语言老师"],
        )
        self.assertEqual(
            result["Source"].tolist(),
            [
                "But I had an amazing Russian teacher,",
                "an amazing Korean teacher,",
                "and an amazing alien language teacher in Steven Spielberg,",
            ],
        )
        self.assertEqual(result.iloc[0]["display_timestamp"][0], 15.50)
        self.assertEqual(result.iloc[-1]["display_timestamp"][1], 22.58)
        self.assertNotIn("Steven", result.iloc[1]["Source"])
        self.assertIn("Steven Spielberg", result.iloc[2]["Source"])
        self.assertIn("史蒂文·斯皮尔伯格", result.iloc[2]["Translation"])
        self.assertNotIn("史蒂文·斯皮尔伯", result.iloc[1]["Translation"])

    def test_timeline_split_keeps_cjk_middle_dot_name_and_source_name_together(self):
        df = pd.DataFrame([
            {
                "Source": "I worked with Steven Spielberg on a language scene and learned a lot.",
                "Translation": "我和史蒂文·斯皮尔伯格合作完成语言场景 也学到了很多",
                "display_timestamp": (10.0, 15.2),
                "speech_timestamp": (10.0, 15.2),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=576, target_height=1024)

        self.assertTrue(any("史蒂文·斯皮尔伯格" in text for text in result["Translation"].tolist()))
        self.assertFalse(any(text.endswith("史蒂文·斯皮尔伯") for text in result["Translation"].tolist()))
        self.assertFalse(any(text.startswith("格") for text in result["Translation"].tolist()))
        self.assertTrue(any("Steven Spielberg" in text for text in result["Source"].tolist()))

    def test_source_phrase_split_uses_punctuation_not_word_count(self):
        df = pd.DataFrame([
            {
                "Source": "Emily, let's talk a little bit about your language",
                "Translation": "艾米莉 我们稍微谈谈",
                "display_timestamp": (0.0, 1.693),
                "speech_timestamp": (0.0, 1.693),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=576, target_height=1024)

        self.assertEqual(len(result), 1)

        repaired = _repair_adjacent_source_phrase_splits(pd.DataFrame([
            {
                "Source": "Emily, let's talk a",
                "Translation": "艾米莉",
                "display_timestamp": (0.0, 0.644),
                "speech_timestamp": (0.0, 0.644),
            },
            {
                "Source": "little bit about your language",
                "Translation": "我们稍微谈谈",
                "display_timestamp": (0.644, 1.693),
                "speech_timestamp": (0.644, 1.693),
            },
        ]))

        self.assertEqual(repaired["Source"].tolist(), ["Emily,", "let's talk a little bit about your language"])

    def test_adjacent_source_repair_does_not_pull_next_sentence_marker_back(self):
        repaired = _repair_adjacent_source_phrase_splits(pd.DataFrame([
            {
                "Source": "because you had to learn a fair bit of pitch -perfect Russian and Korean.",
                "Translation": "因为你要学很多俄语和韩语 还都得说得特别标准",
                "display_timestamp": (2.58, 7.14),
                "speech_timestamp": (2.58, 7.14),
            },
            {
                "Source": "Well, I'm sure the Russians and the",
                "Translation": "不过我想俄罗斯人和韩国人肯定不会觉得",
                "display_timestamp": (7.18, 10.105),
                "speech_timestamp": (7.18, 10.105),
            },
        ]))

        self.assertEqual(
            repaired["Source"].tolist(),
            [
                "because you had to learn a fair bit of pitch -perfect Russian and Korean.",
                "Well, I'm sure the Russians and the",
            ],
        )

    def test_adjacent_source_repair_does_not_isolate_discourse_marker(self):
        repaired = _repair_adjacent_source_phrase_splits(pd.DataFrame([
            {
                "Source": "Well, I'm sure the Russians and the",
                "Translation": "不过我想俄罗斯人和韩国人肯定不会觉得",
                "display_timestamp": (7.18, 10.105),
                "speech_timestamp": (7.18, 10.105),
            },
            {
                "Source": "Koreans wouldn't say it was pitch -perfect,",
                "Translation": "我发音完美",
                "display_timestamp": (10.105, 13.413),
                "speech_timestamp": (10.105, 13.413),
            },
        ]))

        self.assertEqual(
            repaired["Source"].tolist(),
            [
                "Well, I'm sure the Russians and the",
                "Koreans wouldn't say it was pitch -perfect,",
            ],
        )


if __name__ == "__main__":
    unittest.main()
