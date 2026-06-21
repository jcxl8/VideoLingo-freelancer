import unittest

from core.subtitle_layout import Box, PortraitMetrics, layout_bilingual, layout_hardsub


class PortraitLayoutGeometryTest(unittest.TestCase):
    def setUp(self):
        self.metrics = PortraitMetrics(
            width=576,
            height=1024,
            source_font_size=45,
            translation_font_size=45,
            hardsub_translation_font_size=45,
            watermark_font_size=27,
            side_margin=20,
            safe_vertical_margin=10,
            subtitle_gap=8,
            watermark_gap=10,
        )

    def test_positive_bilingual_offset_moves_complete_block_up(self):
        zero = layout_bilingual(self.metrics, 1, 2, "bilingual_trans_top", 0, 0)
        shifted = layout_bilingual(self.metrics, 1, 2, "bilingual_trans_top", 40, 0)

        self.assertEqual(shifted.source.top, zero.source.top - 40)
        self.assertEqual(shifted.translation.top, zero.translation.top - 40)

    def test_lower_hardsub_prefers_watermark_and_translation_below(self):
        hard = Box(92, 619, 411, 735)
        layout = layout_hardsub(self.metrics, hard, 2, 0, 0)

        self.assertGreaterEqual(layout.watermark.top, hard.bottom + 8)
        self.assertGreaterEqual(layout.translation.top, layout.watermark.bottom + 10)

    def test_extreme_watermark_offset_cannot_overlap_hardsub(self):
        hard = Box(92, 619, 411, 735)
        layout = layout_hardsub(self.metrics, hard, 2, 0, -200)

        self.assertFalse(layout.watermark.intersects(hard))
        self.assertFalse(layout.watermark.intersects(layout.translation))

    def test_hardsub_always_prefers_below_when_complete_group_fits(self):
        hard = Box(100, 280, 480, 340)
        layout = layout_hardsub(self.metrics, hard, 2, 0, 0)

        self.assertGreaterEqual(layout.watermark.top, hard.bottom + 8)
        self.assertGreaterEqual(layout.translation.top, layout.watermark.bottom + 10)

    def test_hardsub_falls_back_above_when_lower_group_cannot_fit(self):
        hard = Box(100, 850, 480, 940)
        layout = layout_hardsub(self.metrics, hard, 2, 0, 0)

        self.assertLessEqual(layout.watermark.bottom + 8, hard.top)
        self.assertLessEqual(layout.translation.bottom + 10, layout.watermark.top)

    def test_all_boxes_stay_inside_safe_frame(self):
        hard = Box(92, 619, 411, 735)
        layout = layout_hardsub(self.metrics, hard, 3, -500, 500)

        for box in (layout.translation, layout.watermark):
            self.assertGreaterEqual(box.top, 10)
            self.assertLessEqual(box.bottom, 1014)


if __name__ == "__main__":
    unittest.main()
