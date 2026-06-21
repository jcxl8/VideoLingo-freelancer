import unittest

from core import _7_sub_into_vid as subvid
from core._7_sub_into_vid import _estimate_text_width_px, _wrap_subtitle_lines


class SubtitleAssWrappingTest(unittest.TestCase):
    def test_long_chinese_subtitle_does_not_overflow_portrait_safe_width(self):
        text = "根据《国内税收法典》 您可从应税收入中扣除 工作空间占房屋面积比例对应的费用"
        target_width = 540
        font_size = 36
        margin_h = 20
        max_width = target_width - margin_h * 2

        lines = _wrap_subtitle_lines(text, target_width, font_size, margin_h)

        self.assertGreaterEqual(len(lines), 3)
        for line in lines:
            self.assertLessEqual(_estimate_text_width_px(line, font_size), max_width)
            self.assertGreaterEqual(len(line.strip()), 3)

    def test_short_chinese_subtitle_stays_single_line(self):
        text = "她可不叫丽莎"
        lines = _wrap_subtitle_lines(text, 540, 36, 20)

        self.assertEqual(lines, [text])

    def test_long_english_subtitle_stays_within_safe_width(self):
        text = "As you will see there is far to go but after December's breakthrough we were invited to tour the lab"
        target_width = 1920
        font_size = 44
        margin_h = 96
        max_width = target_width - margin_h * 2

        lines = _wrap_subtitle_lines(text, target_width, font_size, margin_h)

        self.assertGreaterEqual(len(lines), 2)
        for line in lines:
            self.assertLessEqual(_estimate_text_width_px(line, font_size), max_width)

    def test_chinese_middle_dot_person_name_is_not_split_by_visual_wrapping(self):
        text = "还有史蒂文·斯皮尔伯格当我的外星语言老师"
        _, trans_size = subvid._portrait_font_sizes(1920)
        lines = _wrap_subtitle_lines(
            text,
            target_width=1920,
            font_size=trans_size,
            margin_h=subvid._portrait_safe_side_margin(1920),
        )

        self.assertTrue(any("史蒂文·斯皮尔伯格" in line for line in lines), lines)
        self.assertFalse(any(line.endswith("史蒂文·斯皮尔伯") for line in lines), lines)
        self.assertFalse(any(line.startswith("格") for line in lines), lines)
        self.assertEqual(lines, ["还有史蒂文·斯皮尔伯格", "当我的外星语言老师"])

    def test_chinese_person_name_followed_by_apposition_wraps_after_name(self):
        text = "还有史蒂文·斯皮尔伯格这位很棒的外星语老师"
        _, trans_size = subvid._portrait_font_sizes(1920)
        lines = _wrap_subtitle_lines(
            text,
            target_width=1920,
            font_size=trans_size,
            margin_h=subvid._portrait_safe_side_margin(1920),
        )

        self.assertEqual(lines, ["还有史蒂文·斯皮尔伯格", "这位很棒的外星语老师"])
        self.assertFalse(any(line.endswith("外星") for line in lines), lines)
        self.assertFalse(any(line.startswith("语老师") for line in lines), lines)

    def test_chinese_teacher_phrase_wraps_on_semantic_boundary(self):
        text = "不过，我有位很棒的俄语老师很棒的韩语老师"
        _, trans_size = subvid._portrait_font_sizes(1920)
        lines = _wrap_subtitle_lines(
            text,
            target_width=1920,
            font_size=trans_size,
            margin_h=subvid._portrait_safe_side_margin(1920),
        )

        self.assertEqual(lines, ["不过，我有位很棒的俄语老师", "很棒的韩语老师"])
        self.assertFalse(any(line.endswith("俄") for line in lines), lines)
        self.assertFalse(any(line.startswith("语老师") for line in lines), lines)


if __name__ == "__main__":
    unittest.main()
