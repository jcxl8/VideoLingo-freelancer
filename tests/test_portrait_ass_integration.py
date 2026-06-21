import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import _7_sub_into_vid as subvid


def _write_srt(path, text):
    with open(path, "w", encoding="utf-8") as file:
        file.write(f"1\n00:00:01,000 --> 00:00:03,000\n{text}\n")


def _write_entries(path, texts):
    with open(path, "w", encoding="utf-8") as file:
        for index, text in enumerate(texts, 1):
            file.write(
                f"{index}\n00:00:0{index},000 --> 00:00:0{index + 1},000\n{text}\n\n"
            )


class PortraitAssIntegrationTest(unittest.TestCase):
    def test_portrait_ass_uses_independent_configured_sizes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "src.srt")
            trans = os.path.join(tmpdir, "trans.srt")
            _write_srt(src, "Source line")
            _write_srt(trans, "译文")
            style = subvid.PortraitStyleConfig(
                source_font_size=50,
                translation_font_size=62,
                hardsub_translation_font_size=66,
            )
            with patch.object(subvid, "OUTPUT_DIR", tmpdir):
                with patch.object(subvid, "_portrait_style_config", return_value=style):
                    ass_path = subvid._create_portrait_bilingual_ass(
                        src, trans, "bilingual_trans_top", 576, 1024
                    )
            content = Path(ass_path).read_text(encoding="utf-8")

        self.assertIn(f"Style: SrcTop,{subvid.FONT_NAME},50", content)
        self.assertIn(f"Style: TransTop,{subvid.TRANS_FONT_NAME},62", content)

    def test_hardsub_ass_uses_dedicated_size_and_below_alignment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trans = os.path.join(tmpdir, "trans.srt")
            _write_srt(trans, "我们只想让你知道")
            style = subvid.PortraitStyleConfig(
                source_font_size=45,
                translation_font_size=45,
                hardsub_translation_font_size=60,
            )
            with patch.object(subvid, "OUTPUT_DIR", tmpdir):
                with patch.object(subvid, "_portrait_style_config", return_value=style):
                    ass_path = subvid._create_translation_avoiding_hardsub_ass(
                        trans,
                        576,
                        1024,
                        {"left": 92, "top": 619, "right": 411, "bottom": 735},
                    )
            content = Path(ass_path).read_text(encoding="utf-8")

        self.assertIn("Style: TransBelowHardSub", content)
        self.assertIn(f"{subvid.TRANS_FONT_NAME},60", content)
        self.assertIn(",8,", content)

    def test_portrait_watermark_uses_same_hardsub_layout(self):
        box = {"left": 92, "top": 619, "right": 411, "bottom": 735}
        layout = subvid._portrait_layout_for_subtitles(
            None,
            None,
            "translation_only",
            576,
            1024,
            box,
            translation_line_count=2,
        )
        result = subvid._watermark_drawtext_filter(
            1024,
            layout=subvid.SUBTITLE_LAYOUT_PORTRAIT,
            target_width=576,
            source_hardsub_box=box,
            portrait_layout=layout,
        )

        self.assertIn(f"y={layout.watermark.top}", result)
        self.assertGreaterEqual(layout.watermark.top, box["bottom"] + 8)
        self.assertGreaterEqual(layout.translation.top, layout.watermark.bottom + 10)

    def test_bilingual_dialogue_margins_follow_each_entries_line_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "src.srt")
            trans = os.path.join(tmpdir, "trans.srt")
            _write_entries(src, ("Short source", "Short source"))
            _write_entries(
                trans,
                (
                    "短译文",
                    "这是一条明显更长的中文译文，用来强制字幕在竖屏安全宽度内换成两行显示",
                ),
            )
            with patch.object(subvid, "OUTPUT_DIR", tmpdir):
                ass_path = subvid._create_portrait_bilingual_ass(
                    src, trans, "bilingual_src_top", 576, 1024
                )
            dialogue = [
                line for line in Path(ass_path).read_text(encoding="utf-8").splitlines()
                if line.startswith("Dialogue:") and ",SrcTop," in line
            ]

        self.assertEqual(len(dialogue), 2)
        margins = [int(line.split(",")[7]) for line in dialogue]
        self.assertNotEqual(margins[0], margins[1])

    def test_hardsub_entries_can_use_different_geometry_groups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            trans = os.path.join(tmpdir, "trans.srt")
            _write_entries(
                trans,
                (
                    "短译文",
                    "这是一条非常长的中文译文，需要在竖屏画面中换成很多行，从而无法继续放在硬字幕下方。"
                    "为了验证逐条布局，文本还要继续延伸，并保持足够长度，确保完整字幕组只能回退到硬字幕上方。"
                    "这里再补充一段内容，让换行数量稳定超过下方安全区域所能容纳的高度。",
                ),
            )
            with patch.object(subvid, "OUTPUT_DIR", tmpdir):
                ass_path = subvid._create_translation_avoiding_hardsub_ass(
                    trans,
                    576,
                    1024,
                    {"left": 92, "top": 690, "right": 411, "bottom": 735},
                )
            dialogue = [
                line for line in Path(ass_path).read_text(encoding="utf-8").splitlines()
                if line.startswith("Dialogue:")
            ]

        self.assertEqual(len(dialogue), 2)
        styles = [line.split(",")[3] for line in dialogue]
        self.assertNotEqual(styles[0], styles[1])


if __name__ == "__main__":
    unittest.main()
