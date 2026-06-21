import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core import _7_sub_into_vid as subvid


def _write_srt(path, text):
    with open(path, "w", encoding="utf-8") as file:
        file.write(f"1\n00:00:01,000 --> 00:00:03,000\n{text}\n")


class SubtitleFilterParityTest(unittest.TestCase):
    def test_portrait_settings_do_not_change_landscape_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "src.srt")
            trans = os.path.join(tmpdir, "trans.srt")
            _write_srt(src, "Source")
            _write_srt(trans, "译文")
            with patch.object(subvid, "OUTPUT_DIR", tmpdir), patch.object(
                subvid,
                "_subtitle_layout_for_video",
                return_value=subvid.SUBTITLE_LAYOUT_LANDSCAPE,
            ):
                baseline = subvid._video_filter_for_subtitles(
                    1920, 1080, src, trans, "bilingual_trans_top"
                )
                extreme = subvid.PortraitStyleConfig(
                    source_font_size=120,
                    translation_font_size=140,
                    hardsub_translation_font_size=140,
                    bilingual_offset=300,
                    hardsub_translation_offset=-300,
                    watermark_font_size=80,
                    watermark_offset=400,
                )
                with patch.object(
                    subvid, "_portrait_style_config", return_value=extreme
                ):
                    changed = subvid._video_filter_for_subtitles(
                        1920, 1080, src, trans, "bilingual_trans_top"
                    )
        self.assertEqual(changed, baseline)

    def test_preview_and_burn_use_shared_filter_builder(self):
        capture = MagicMock()
        capture.get.side_effect = [576, 1024, 576, 1024]
        process = MagicMock()
        process.wait.return_value = 0
        process.returncode = 0
        with tempfile.TemporaryDirectory() as tmpdir:
            video = os.path.join(tmpdir, "video.mp4")
            src = os.path.join(tmpdir, "src.srt")
            trans = os.path.join(tmpdir, "trans.srt")
            preview = os.path.join(tmpdir, "preview.jpg")
            output = os.path.join(tmpdir, "output.mp4")
            open(video, "wb").close()
            _write_srt(src, "Source")
            _write_srt(trans, "译文")
            with patch.object(subvid.cv2, "VideoCapture", return_value=capture), patch.object(
                subvid, "_video_filter_for_subtitles", return_value="shared-filter"
            ) as shared, patch.object(
                subvid.subprocess, "run", return_value=MagicMock(returncode=0)
            ), patch.object(
                subvid.subprocess, "Popen", return_value=process
            ), patch.object(
                subvid, "load_key", side_effect=lambda key: True if key == "burn_subtitles" else False
            ):
                subvid.render_subtitle_preview_frame(
                    video, preview, src, trans, "bilingual_trans_top", watermark_enabled=True
                )
                subvid.burn_subtitles_to_video(
                    video, output, src, trans, "bilingual_trans_top", watermark_enabled=True
                )

        self.assertEqual(shared.call_count, 2)
        self.assertEqual(shared.call_args_list[0].args, shared.call_args_list[1].args)
        self.assertEqual(shared.call_args_list[0].kwargs, shared.call_args_list[1].kwargs)


if __name__ == "__main__":
    unittest.main()
