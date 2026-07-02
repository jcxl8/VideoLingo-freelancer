import unittest
import tempfile
from pathlib import Path

import pandas as pd

from core._6_gen_sub import (
    align_timestamp,
    _drop_likely_standalone_ack_hallucinations,
    _repair_leading_sentence_continuations,
    _merge_short_adjacent_subtitles,
    _repair_adjacent_source_phrase_splits,
    _should_split_long_display_subtitle,
    _split_leading_program_title_question,
    _split_long_display_subtitles,
)


class LongSubtitleTimelineSplitTest(unittest.TestCase):
    def test_landscape_long_semantic_subtitle_splits_even_with_comfortable_cps(self):
        parts = _should_split_long_display_subtitle(
            "好友用主页分享近况、交换照片， 联手推动政治议题，或只玩远程拼字游戏",
            (21.40, 31.45),
            1920,
            1080,
        )

        self.assertEqual(parts, ["好友用主页分享近况", "交换照片", "联手推动政治议题", "或只玩远程拼字游戏"])

    def test_and_among_them_clause_splits_on_word_anchor(self):
        words = [
            ("Zuckerberg", 415.09, 415.73),
            ("says", 415.73, 415.97),
            ("there", 415.97, 416.31),
            ("seem", 416.31, 416.51),
            ("to", 416.51, 416.69),
            ("be", 416.69, 416.85),
            ("more", 416.85, 417.17),
            ("Republicans", 417.17, 417.73),
            ("on", 417.73, 418.13),
            ("the", 418.13, 418.25),
            ("site", 418.25, 418.53),
            ("than", 418.53, 418.77),
            ("Democrats.", 418.77, 419.25),
            ("and", 419.25, 419.93),
            ("among", 419.93, 420.29),
            ("them,", 420.29, 420.65),
            ("Barack", 420.77, 421.25),
            ("Obama,", 421.25, 421.87),
            ("with", 421.97, 422.23),
            ("his", 422.23, 422.39),
            ("young", 422.39, 422.63),
            ("person's", 422.63, 423.19),
            ("following,", 423.19, 423.55),
            ("is", 423.71, 424.09),
            ("hugely", 424.09, 424.61),
            ("popular.", 424.61, 425.09),
        ]
        df_words = pd.DataFrame(words, columns=["text", "start", "end"])
        df = pd.DataFrame([{
            "Source": "Zuckerberg says there seem to be more Republicans on the site than Democrats and among them, Barack Obama with his young person's following, is hugely popular.",
            "Translation": "扎克伯格说，网站上的共和党人似乎比民主党人多 其中，巴拉克·奥巴马靠年轻人的追捧，人气极高",
            "start_word_idx": 0,
            "end_word_idx": 25,
            "start_word": "Zuckerberg",
            "end_word": "popular.",
            "speech_timestamp": (415.09, 425.09),
            "display_timestamp": (415.09, 425.34),
            "speech_duration": 10.0,
            "duration": 10.25,
        }])

        result = _split_long_display_subtitles(df, 1920, 1080, df_words)

        self.assertEqual(result["Source"].tolist(), [
            "Zuckerberg says there seem to be more Republicans on the site than Democrats",
            "and among them, Barack Obama with his young person's following, is hugely popular.",
        ])
        self.assertEqual(result["Translation"].tolist(), [
            "扎克伯格说，网站上的共和党人似乎比民主党人多",
            "其中，巴拉克·奥巴马靠年轻人的追捧，人气极高",
        ])
        self.assertEqual(result["display_timestamp"].tolist(), [(415.09, 419.25), (419.25, 425.34)])

    def test_but_clause_splits_hoodie_sentence_on_word_anchor(self):
        words = [
            ("He", 764.58, 764.96),
            ("might", 764.96, 765.20),
            ("still", 765.20, 765.50),
            ("wear", 765.50, 765.74),
            ("a", 765.74, 765.92),
            ("hoodie", 765.92, 766.16),
            ("and", 766.16, 766.48),
            ("no", 766.48, 766.64),
            ("socks,", 766.64, 767.06),
            ("but", 767.36, 767.88),
            ("he's", 767.88, 768.12),
            ("becoming", 768.12, 768.54),
            ("a", 768.54, 768.80),
            ("suit", 768.80, 769.16),
            ("as", 769.16, 769.92),
            ("he", 769.92, 770.04),
            ("ponders", 770.04, 770.58),
            ("whether", 770.58, 770.90),
            ("to", 770.90, 771.14),
            ("take", 771.14, 771.40),
            ("his", 771.40, 771.56),
            ("company", 771.56, 771.86),
            ("public", 771.86, 772.36),
            ("this", 772.36, 772.88),
            ("year.", 772.88, 773.18),
        ]
        df_words = pd.DataFrame(words, columns=["text", "start", "end"])
        df = pd.DataFrame([{
            "Source": "He might still wear a hoodie and no socks, but he's becoming a suit as he ponders whether to take his company public this year.",
            "Translation": "他可能还穿着连帽衫，不穿袜子，但已初具高管风范， 他正考虑是否今年让公司上市",
            "start_word_idx": 0,
            "end_word_idx": 24,
            "start_word": "He",
            "end_word": "year.",
            "speech_timestamp": (764.58, 773.18),
            "display_timestamp": (764.58, 773.43),
            "speech_duration": 8.6,
            "duration": 8.85,
        }])

        result = _split_long_display_subtitles(df, 1920, 1080, df_words)

        self.assertEqual(result["Translation"].tolist(), [
            "他可能还穿着连帽衫 不穿袜子",
            "但已初具高管风范 他正考虑是否今年让公司上市",
        ])
        self.assertEqual(result["display_timestamp"].tolist(), [(764.58, 767.36), (767.36, 773.43)])

    def test_but_clause_splits_age_experience_sentence_on_word_anchor(self):
        words = [
            ("There", 793.38, 793.86),
            ("are", 793.86, 794.82),
            ("definitely", 794.82, 795.04),
            ("elements", 795.04, 795.42),
            ("of", 795.42, 795.76),
            ("experience", 795.76, 796.38),
            ("and", 796.38, 796.90),
            ("stuff", 796.90, 797.24),
            ("that", 797.24, 797.56),
            ("someone", 797.56, 798.38),
            ("who's", 798.38, 798.98),
            ("my", 798.98, 799.10),
            ("age", 799.10, 799.28),
            ("wouldn't", 799.28, 799.60),
            ("have,", 799.60, 799.82),
            ("but", 800.00, 800.26),
            ("there", 800.26, 800.44),
            ("are", 800.44, 800.54),
            ("also", 800.54, 800.74),
            ("things", 800.74, 800.96),
            ("that", 800.96, 801.28),
            ("I", 801.28, 801.62),
            ("can", 801.62, 801.78),
            ("do", 801.78, 801.98),
            ("that", 801.98, 802.26),
            ("other", 802.26, 802.56),
            ("people", 802.56, 802.88),
            ("wouldn't", 802.88, 803.30),
            ("necessarily", 803.30, 803.56),
            ("be", 803.56, 803.84),
            ("able", 803.84, 804.02),
            ("to.", 804.02, 804.18),
        ]
        df_words = pd.DataFrame(words, columns=["text", "start", "end"])
        df = pd.DataFrame([{
            "Source": "There are definitely elements of experience and stuff that someone who's my age wouldn't have, but there are also things that I can do that other people wouldn't necessarily be able to.",
            "Translation": "我这个年纪的人肯定缺少一些经验 但也有一些事情我能做，别人却未必能做到",
            "start_word_idx": 0,
            "end_word_idx": 31,
            "start_word": "There",
            "end_word": "to.",
            "speech_timestamp": (793.38, 804.18),
            "display_timestamp": (793.38, 804.43),
            "speech_duration": 10.8,
            "duration": 11.05,
        }])

        result = _split_long_display_subtitles(df, 1920, 1080, df_words)

        self.assertEqual(result["Translation"].tolist(), [
            "我这个年纪的人肯定缺少一些经验",
            "但也有一些事情我能做 别人却未必能做到",
        ])
        self.assertEqual(result["display_timestamp"].tolist(), [(793.38, 800.00), (800.00, 804.43)])

    def test_ellipsis_question_answer_splits_into_three_semantic_rows(self):
        words = [
            ("So", 588.85, 588.85),
            ("it", 588.85, 589.23),
            ("would", 589.23, 589.35),
            ("go", 589.35, 589.61),
            ("to...", 589.61, 589.69),
            ("But", 589.69, 589.69),
            ("with", 589.69, 589.69),
            ("me", 589.69, 589.73),
            ("in", 589.73, 589.99),
            ("the", 589.99, 590.01),
            ("ad?", 590.01, 590.27),
            ("Yeah,", 590.57, 590.91),
            ("but", 590.95, 591.03),
            ("that", 591.03, 591.17),
            ("would", 591.17, 591.41),
            ("basically", 591.41, 591.77),
            ("be", 591.77, 592.01),
            ("the", 592.01, 592.21),
            ("ad.", 592.21, 592.39),
        ]
        df_words = pd.DataFrame(words, columns=["text", "start", "end"])
        df = pd.DataFrame([{
            "Source": "So it would go to... But with me in the ad? Yeah, but that would basically be the ad.",
            "Translation": "它会发送，我会出现吗？那就是广告。",
            "start_word_idx": 0,
            "end_word_idx": 18,
            "start_word": "So",
            "end_word": "ad.",
            "speech_timestamp": (588.85, 592.39),
            "display_timestamp": (588.85, 592.65),
            "speech_duration": 3.54,
            "duration": 3.80,
        }])

        result = _split_long_display_subtitles(df, 1920, 1080, df_words)

        self.assertEqual(result["Source"].tolist(), [
            "So it would go to...",
            "But with me in the ad?",
            "Yeah, but that would basically be the ad.",
        ])
        self.assertEqual(result["Translation"].tolist(), ["它会发送", "我会出现吗？", "那就是广告"])
        self.assertEqual(result["display_timestamp"].tolist(), [(588.85, 589.69), (589.69, 590.57), (590.57, 592.65)])

    def test_leading_60_minutes_rewind_title_splits_from_question(self):
        df_words = pd.DataFrame(
            [
                ("60", 0.32, 0.92),
                ("Minutes", 0.92, 1.30),
                ("Rewind", 1.30, 2.32),
                ("Are", 3.72, 4.02),
                ("you", 4.02, 4.22),
                ("on", 4.22, 4.42),
                ("Facebook", 4.42, 4.84),
                ("yet?", 4.84, 5.22),
            ],
            columns=["text", "start", "end"],
        )
        df = pd.DataFrame([
            {
                "Source": "60 Minutes Rewind Are you on Facebook yet?",
                "Translation": "60 Minutes Rewind 你上 Facebook 了吗？",
                "start_word_idx": 0,
                "end_word_idx": 7,
                "start_word": "60",
                "end_word": "yet?",
                "speech_timestamp": (0.32, 5.22),
                "display_timestamp": (0.319, 5.40),
                "speech_duration": 4.90,
                "duration": 5.08,
            }
        ])

        result = _split_leading_program_title_question(df, df_words)

        self.assertEqual(result["Source"].tolist(), ["60 Minutes Rewind", "Are you on Facebook yet?"])
        self.assertEqual(result["Translation"].tolist(), ["60 Minutes Rewind", "你上 Facebook 了吗？"])
        self.assertEqual(result["display_timestamp"].tolist(), [(0.319, 2.32), (3.72, 5.40)])

    def test_trans_src_export_preserves_canonical_source_text(self):
        df_words = pd.DataFrame(
            [
                ("Yes.", 0.0, 0.2),
                ("Too", 0.2, 0.4),
                ("many", 0.4, 0.6),
                ("people", 0.6, 0.8),
                ("sacrificed", 0.8, 1.0),
                ("so", 1.0, 1.2),
                ("that", 1.2, 1.4),
                ("I", 1.4, 1.6),
                ("could", 1.6, 1.8),
                ("be", 1.8, 2.0),
                ("here.", 2.0, 2.2),
                ("The", 3.0, 3.2),
                ("next", 3.2, 3.4),
                ("line", 3.4, 3.6),
                ("stays", 3.6, 3.8),
                ("normal.", 3.8, 4.0),
            ],
            columns=["text", "start", "end"],
        )
        source = "Yes. Too many people sacrificed so that I could be here."
        translation = "是的 太多人为了我能站在这里而牺牲了"
        df_translate = pd.DataFrame([
            {"Source": source, "Translation": translation},
            {"Source": "The next line stays normal.", "Translation": "下一句保持正常"},
        ])

        with tempfile.TemporaryDirectory() as directory:
            align_timestamp(
                df_words,
                df_translate,
                [("trans_src.srt", ["Translation", "Source"])],
                directory,
            )

            exported = (Path(directory) / "trans_src.srt").read_text(encoding="utf-8")

        self.assertIn(f"{translation}\n{source}", exported)

    def test_leading_actually_fragment_moves_to_previous_sentence(self):
        df_words = pd.DataFrame(
            [
                ("I", 118.22, 118.34),
                ("don't", 118.34, 118.62),
                ("know.", 118.62, 118.90),
                ("I", 118.90, 119.02),
                ("might", 119.02, 119.24),
                ("use", 119.24, 119.44),
                ("it.", 119.44, 120.407),
                ("actually.", 121.0, 121.3),
                ("They're", 121.3, 121.7),
                ("not", 121.7, 121.9),
                ("lyrics,", 121.9, 122.4),
                ("really.", 122.4, 123.199),
            ],
            columns=["text", "start", "end"],
        )
        df_translate = pd.DataFrame([
            {
                "Source": "I don't know. I might use it.",
                "Translation": "不知道 没准会用上",
            },
            {
                "Source": "actually. They're not lyrics, really.",
                "Translation": "其实这根本不算歌词",
            },
        ])

        df_trans_time = df_translate.copy()
        df_trans_time["start_word_idx"] = [0, 7]
        df_trans_time["end_word_idx"] = [6, 11]
        df_trans_time["start_word"] = ["I", "actually."]
        df_trans_time["end_word"] = ["it.", "really."]
        df_trans_time["speech_timestamp"] = [(118.22, 120.407), (121.0, 123.199)]
        df_trans_time["display_timestamp"] = [(118.22, 120.407), (121.0, 123.199)]
        df_trans_time["speech_duration"] = [2.187, 2.199]

        result = _repair_leading_sentence_continuations(df_trans_time, df_words)

        self.assertEqual(result.iloc[0]["Source"], "I don't know. I might use it actually.")
        self.assertEqual(result.iloc[0]["Translation"], "我也说不准 其实没准会用上")
        self.assertEqual(result.iloc[1]["Source"], "They're not lyrics, really.")
        self.assertEqual(result.iloc[1]["Translation"], "这根本不算歌词")
        self.assertEqual(result.iloc[0]["display_timestamp"], (118.22, 121.3))
        self.assertEqual(result.iloc[1]["display_timestamp"], (121.3, 123.199))

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

    def test_question_sentence_keeps_matching_chinese_question_translation(self):
        df = pd.DataFrame([
            {
                "Source": (
                    "What rhymes with orange? If you're taking the word at face value "
                    "and you just say orange nothing is going to rhyme with it exactly."
                ),
                "Translation": (
                    "什么词和 orange 押韵？ 如果你只按字面发音的话 直接读 orange "
                    "那就没什么词能跟它完全押韵了"
                ),
                "display_timestamp": (15.54, 24.39),
                "speech_timestamp": (15.54, 24.39),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=1920, target_height=1080)

        self.assertEqual(
            result["Source"].tolist(),
            [
                "What rhymes with orange?",
                (
                    "If you're taking the word at face value and you just say orange "
                    "nothing is going to rhyme with it exactly."
                ),
            ],
        )
        self.assertEqual(
            result["Translation"].tolist(),
            [
                "什么词和 orange 押韵？",
                "如果你只按字面发音的话 直接读 orange 那就没什么词能跟它完全押韵了",
            ],
        )

    def test_landscape_long_clause_subtitle_splits_into_timed_semantic_rows(self):
        df = pd.DataFrame([
            {
                "Source": (
                    "Like, people say that the word orange doesn't rhyme with anything, and that "
                    "kind of pisses me off because I can think of a lot of things that rhyme with orange."
                ),
                "Translation": (
                    "La gente dice que 'naranja' no rima con nada, y eso me enfurece "
                    "porque puedo pensar en muchas palabras que riman con naranja."
                ),
                "display_timestamp": (5.1, 15.5),
                "speech_timestamp": (5.1, 15.46),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=1920, target_height=1080)

        self.assertEqual(
            result["Source"].tolist(),
            [
                "Like, people say that the word orange doesn't rhyme with anything,",
                "and that kind of pisses me off",
                "because I can think of a lot of things that rhyme with orange.",
            ],
        )
        self.assertEqual(
            result["Translation"].tolist(),
            [
                "La gente dice que 'naranja' no rima con nada",
                "y eso me enfurece",
                "porque puedo pensar en muchas palabras que riman con naranja.",
            ],
        )
        self.assertEqual(result.iloc[0]["display_timestamp"][0], 5.1)
        self.assertEqual(result.iloc[-1]["display_timestamp"][1], 15.5)
        self.assertEqual(result.iloc[0]["display_timestamp"][1], result.iloc[1]["display_timestamp"][0])
        self.assertEqual(result.iloc[1]["display_timestamp"][1], result.iloc[2]["display_timestamp"][0])

    def test_rhyme_with_anything_chinese_clause_stays_with_first_source_clause(self):
        df = pd.DataFrame([
            {
                "Source": (
                    "Like, people say that the word orange doesn't rhyme with anything, and that "
                    "kind of pisses me off because I can think of a lot of things that rhyme with orange."
                ),
                "Translation": (
                    "比如人们常说 orange 这个词没法押韵 跟任何词都押不上韵，"
                    "这点真让我火大 因为我能想到很多词跟 orange 押韵"
                ),
                "display_timestamp": (5.1, 15.5),
                "speech_timestamp": (5.1, 15.5),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=1920, target_height=1080)

        self.assertEqual(
            result["Translation"].tolist(),
            [
                "比如人们常说 orange 这个词没法押韵 跟任何词都押不上韵",
                "这点真让我火大",
                "因为我能想到很多词跟 orange 押韵",
            ],
        )

    def test_parallel_how_much_clause_splits_after_sentence_boundary(self):
        df = pd.DataFrame([
            {
                "Source": (
                    "We'll find out, I guess. But I think one thing that is very different is "
                    "how much people care about other people how much people want to interact with other people"
                ),
                "Translation": (
                    "Acho que vamos descobrir. Mas acho que algo muito diferente é o quanto "
                    "pessoas se importam com outras, quanto querem interagir"
                ),
                "display_timestamp": (1.88, 8.92),
                "speech_timestamp": (1.88, 8.92),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=1920, target_height=1080)

        self.assertEqual(
            result["Source"].tolist(),
            [
                "We'll find out, I guess.",
                "But I think one thing that is very different is how much people care about other people",
                "how much people want to interact with other people",
            ],
        )

        repaired = _repair_adjacent_source_phrase_splits(result)
        self.assertEqual(
            repaired["Source"].tolist(),
            [
                "We'll find out, I guess.",
                "But I think one thing that is very different is how much people care about other people",
                "how much people want to interact with other people",
            ],
        )

    def test_parallel_what_clause_splits_after_sentence_boundary(self):
        df = pd.DataFrame([
            {
                "Source": (
                    "We can imagine and do all sorts of new things. We still have to figure out "
                    "what to do what other people want what other people will find useful."
                ),
                "Translation": (
                    "Poderemos criar todo tipo de novidade. Temos que descobrir o que fazer, "
                    "o que outros querem e o que acharão útil."
                ),
                "display_timestamp": (17.56, 23.52),
                "speech_timestamp": (17.56, 23.18),
            }
        ])

        result = _split_long_display_subtitles(df, target_width=1920, target_height=1080)

        self.assertEqual(
            result["Source"].tolist(),
            [
                "We can imagine and do all sorts of new things.",
                "We still have to figure out what to do",
                "what other people want",
                "what other people will find useful.",
            ],
        )

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

    def test_adjacent_source_repair_preserves_timed_semantic_rows(self):
        repaired = _repair_adjacent_source_phrase_splits(pd.DataFrame([
            {
                "Source": "What rhymes with orange? If you're taking the word at face value and you just say orange",
                "Translation": "¿Qué rima con naranja? Si tomas la palabra al pie de la letra y solo dices 'naranja',",
                "display_timestamp": (15.54, 21.949),
                "speech_timestamp": (15.54, 21.58),
                "start_word_idx": 48,
                "end_word_idx": 64,
            },
            {
                "Source": "nothing is going to rhyme with it exactly.",
                "Translation": "nada va a rimar exactamente.",
                "display_timestamp": (22.4, 25.081),
                "speech_timestamp": (22.4, 24.14),
                "start_word_idx": 65,
                "end_word_idx": 72,
            },
        ]))

        self.assertEqual(
            repaired["Source"].tolist(),
            [
                "What rhymes with orange? If you're taking the word at face value and you just say orange",
                "nothing is going to rhyme with it exactly.",
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
