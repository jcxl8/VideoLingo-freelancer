import os
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from core import _7_sub_into_vid as subvid


class HardSubtitlePlacementTest(unittest.TestCase):
    def test_detected_lower_hardsub_prefers_translation_below(self):
        box = {"top": 1320, "bottom": 1430}

        self.assertEqual(
            subvid._hardsub_translation_placement(box, target_height=1920),
            "below",
        )

    def test_detected_upper_hardsub_places_translation_below(self):
        box = {"top": 700, "bottom": 820}

        self.assertEqual(
            subvid._hardsub_translation_placement(box, target_height=1920),
            "below",
        )

    def test_translation_avoiding_hardsub_ass_uses_top_alignment_when_placed_below(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trans_srt = os.path.join(tmpdir, "trans.srt")
            with open(trans_srt, "w", encoding="utf-8") as f:
                f.write(
                    "1\n"
                    "00:00:01,000 --> 00:00:03,000\n"
                    "测试译文\n"
                )

            with patch.object(subvid, "OUTPUT_DIR", tmpdir):
                ass_path = subvid._create_translation_avoiding_hardsub_ass(
                    trans_srt,
                    target_width=1080,
                    target_height=1920,
                    source_hardsub_box={"top": 700, "bottom": 820},
                )

            with open(ass_path, "r", encoding="utf-8") as f:
                ass_content = f.read()

        self.assertIn("Style: TransBelowHardSub", ass_content)
        self.assertIn(",8,", ass_content)
        self.assertIn("Dialogue: 0,0:00:01.00,0:00:03.00,TransBelowHardSub", ass_content)

    def test_portrait_translation_font_is_large_enough_for_vertical_video(self):
        src_576, trans_576 = subvid._portrait_font_sizes(576)
        src_720, trans_720 = subvid._portrait_font_sizes(720)
        src_1080, trans_1080 = subvid._portrait_font_sizes(1080)
        src_1920, trans_1920 = subvid._portrait_font_sizes(1920)

        self.assertGreaterEqual(src_576, 38)
        self.assertGreaterEqual(trans_576, 44)
        self.assertGreaterEqual(src_720, 46)
        self.assertGreaterEqual(trans_720, 54)
        self.assertGreaterEqual(src_1080, 58)
        self.assertGreaterEqual(trans_1080, 64)
        self.assertGreaterEqual(src_1920, 96)
        self.assertGreaterEqual(trans_1920, 108)

    def test_portrait_watermark_scales_for_high_resolution_vertical_video(self):
        with patch.object(subvid, "load_key", return_value=31):
            self.assertEqual(subvid._watermark_font_size_for_video(None), 31)
            self.assertEqual(subvid._watermark_font_size_for_video(576), 31)
            self.assertGreaterEqual(subvid._watermark_font_size_for_video(1920), 64)

    def test_portrait_source_wraps_instead_of_shrinking_long_english_line(self):
        src_size, _ = subvid._portrait_font_sizes(1920)
        text = "because you had to learn a fair bit of pitch -perfect Russian and Korean."

        ass_text, line_count = subvid._wrap_source_subtitle_for_ass(
            text,
            target_width=1920,
            font_size=src_size,
            margin_h=subvid._portrait_safe_side_margin(1920),
        )

        self.assertGreaterEqual(src_size, 96)
        self.assertEqual(line_count, 2)
        self.assertIn(r"\N", ass_text)
        self.assertNotIn(r"\fs66", ass_text)
        self.assertNotIn(r"\fscx96", ass_text)

    def test_prime_movies_profile_uses_saved_position_as_zero_offset(self):
        values = {
            "subtitle_layout_profile": "default",
            "hardsub_translation_offset": 0,
            "watermark_offset": 0,
            "watermark_font_size": 30,
        }

        def fake_load_key(key, default=None):
            return values.get(key, default)

        with patch.object(subvid, "_safe_load_key", side_effect=fake_load_key):
            with patch.object(subvid, "_safe_int_key", side_effect=lambda key, default=0: int(values.get(key, default))):
                with patch.object(subvid, "load_key", side_effect=fake_load_key):
                    self.assertEqual(subvid._effective_hardsub_translation_offset(), 0)
                    self.assertEqual(
                        subvid._effective_watermark_offset(subvid.SUBTITLE_LAYOUT_PORTRAIT),
                        0,
                    )
                    self.assertEqual(subvid._load_watermark_font_size(), 30)

    def test_removed_prime_movies_profile_falls_back_to_default(self):
        with patch.object(subvid, "_safe_load_key", return_value="prime_movies"):
            self.assertEqual(subvid._subtitle_layout_profile(), "default")

    def test_translation_and_watermark_avoid_lower_hardsub(self):
        with patch.object(subvid, "_effective_hardsub_translation_offset", return_value=0):
            with patch.object(subvid, "_effective_watermark_offset", return_value=0):
                geometry = subvid._hardsub_translation_geometry(
                    {"top": 669, "bottom": 695},
                    target_width=576,
                    target_height=1024,
                )

        self.assertEqual(geometry["placement"], "below")
        self.assertGreaterEqual(geometry["watermark_y"], 695 + 8)
        self.assertGreaterEqual(
            geometry["subtitle_y"], geometry["watermark_bottom_y"] + 10
        )

    def test_watermark_offset_changes_preview_and_burn_filter_position(self):
        box = {"top": 669, "bottom": 695}
        with patch.object(subvid, "_effective_hardsub_translation_offset", return_value=0):
            with patch.object(subvid, "_effective_watermark_offset", return_value=0):
                filter_zero = subvid._watermark_drawtext_filter(
                    1024,
                    layout=subvid.SUBTITLE_LAYOUT_PORTRAIT,
                    target_width=576,
                    source_hardsub_box=box,
                )
            with patch.object(subvid, "_effective_watermark_offset", return_value=50):
                filter_shifted = subvid._watermark_drawtext_filter(
                    1024,
                    layout=subvid.SUBTITLE_LAYOUT_PORTRAIT,
                    target_width=576,
                    source_hardsub_box=box,
                )

        self.assertNotEqual(filter_zero, filter_shifted)
        y_zero = int(filter_zero.rsplit("y=", 1)[1])
        y_shifted = int(filter_shifted.rsplit("y=", 1)[1])
        self.assertLessEqual(y_shifted, y_zero)

    def test_watermark_drawtext_uses_custom_name(self):
        with patch.object(subvid, "load_key", side_effect=lambda key: {
            "watermark_text": "Freelancer Studio",
            "landscape_watermark_font_size": 27,
            "landscape_watermark_offset": -100,
        }.get(key)):
            filter_text = subvid._watermark_drawtext_filter(
                1080,
                layout=subvid.SUBTITLE_LAYOUT_LANDSCAPE,
                target_width=1920,
            )

        self.assertIn("text='Freelancer Studio'", filter_text)

    def test_landscape_watermark_positive_offset_moves_up(self):
        def watermark_y(offset):
            with patch.object(subvid, "_effective_watermark_offset", return_value=offset):
                filter_text = subvid._watermark_drawtext_filter(
                    1080,
                    layout=subvid.SUBTITLE_LAYOUT_LANDSCAPE,
                    target_width=1920,
                )
            return int(filter_text.rsplit("y=", 1)[1])

        y_zero = watermark_y(0)
        y_positive = watermark_y(100)
        y_negative = watermark_y(-100)

        self.assertLess(y_positive, y_zero)
        self.assertGreater(y_negative, y_zero)

    def test_landscape_watermark_defaults_to_15px_above_bilingual_subtitles(self):
        self.assertEqual(
            subvid._landscape_watermark_bottom_y(800, -100),
            785,
        )
        self.assertEqual(
            subvid._landscape_watermark_bottom_y(800, -80),
            765,
        )

    def test_landscape_watermark_tracks_each_bilingual_block_height(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_srt = os.path.join(tmpdir, "src.srt")
            trans_srt = os.path.join(tmpdir, "trans.srt")
            for path, text in (
                (src_srt, "Source subtitle\n\n2\n00:00:04,000 --> 00:00:06,000\n" + "A much longer source subtitle that needs multiple rendered lines in the landscape layout " * 4),
                (trans_srt, "译文字幕\n\n2\n00:00:04,000 --> 00:00:06,000\n" + "这是一条明显更长并且需要在横屏画面中显示为多行的中文译文字幕" * 5),
            ):
                with open(path, "w", encoding="utf-8") as file:
                    file.write(f"1\n00:00:01,000 --> 00:00:03,000\n{text}\n")

            values = {
                "landscape_bilingual_translation_offset": 0,
                "landscape_watermark_font_size": 20,
                "landscape_watermark_offset": -100,
            }
            with patch.object(subvid, "OUTPUT_DIR", tmpdir), patch.object(
                subvid, "load_key", side_effect=lambda key: values.get(key, 0)
            ):
                subtitle_tops = subvid._landscape_bilingual_entry_top_ys(
                    src_srt,
                    trans_srt,
                    target_width=1920,
                    target_height=1080,
                )
                ass_path = subvid._create_landscape_watermark_ass(
                    src_srt, trans_srt, 1920, 1080
                )

            with open(ass_path, encoding="utf-8") as file:
                ass_text = file.read()

        self.assertEqual(len(subtitle_tops), 2)
        self.assertNotEqual(subtitle_tops[0], subtitle_tops[1])
        for subtitle_top in subtitle_tops:
            expected_bottom = subtitle_top - 15
            self.assertIn(f"\\pos(960,{expected_bottom})", ass_text)

    def test_translation_and_watermark_avoid_upper_hardsub(self):
        with patch.object(subvid, "_effective_hardsub_translation_offset", return_value=0):
            with patch.object(subvid, "_effective_watermark_offset", return_value=0):
                geometry = subvid._hardsub_translation_geometry(
                    {"top": 280, "bottom": 340},
                    target_width=576,
                    target_height=1024,
                )

        self.assertEqual(geometry["placement"], "below")
        self.assertGreaterEqual(geometry["watermark_y"], 340 + 8)
        self.assertGreaterEqual(
            geometry["subtitle_y"], geometry["watermark_bottom_y"] + 10
        )

    def test_hardsub_detection_ignores_full_width_video_lines(self):
        frame = np.zeros((1024, 576, 3), dtype=np.uint8)
        cv2.putText(
            frame,
            "What are you doing",
            (150, 690),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.line(frame, (0, 925), (575, 925), (255, 255, 255), 8)

        box = subvid._detect_hardsub_box_in_frame(frame)

        self.assertIsNotNone(box)
        self.assertLess(box["top"], 750)
        self.assertLess(box["bottom"], 780)

    def test_global_hardsub_detection_uses_stable_vertical_cluster(self):
        boxes = [
            {"top": 500, "bottom": 512, "left": 160, "right": 500, "score": 500, "lines": 1},
            {"top": 869, "bottom": 877, "left": 46, "right": 277, "score": 2200, "lines": 1},
            {"top": 572, "bottom": 695, "left": 118, "right": 449, "score": 7000, "lines": 2},
            {"top": 670, "bottom": 695, "left": 184, "right": 434, "score": 1800, "lines": 1},
            {"top": 670, "bottom": 689, "left": 208, "right": 366, "score": 1100, "lines": 1},
            {"top": 614, "bottom": 689, "left": 131, "right": 441, "score": 3100, "lines": 2},
            {"top": 663, "bottom": 723, "left": 175, "right": 451, "score": 4000, "lines": 1},
        ]

        fake_frames = [np.zeros((1024, 576, 3), dtype=np.uint8) for _ in boxes]
        with patch.object(subvid, "_sample_video_frames", return_value=fake_frames):
            with patch.object(subvid, "_detect_hardsub_box_in_frame", side_effect=boxes):
                detected = subvid.detect_existing_source_hardsub("fake.mp4")

        self.assertIsNotNone(detected)
        self.assertGreaterEqual(detected["top"], 590)
        self.assertLessEqual(detected["bottom"], 730)
        self.assertLess(detected["height_ratio"], 0.18)


if __name__ == "__main__":
    unittest.main()
