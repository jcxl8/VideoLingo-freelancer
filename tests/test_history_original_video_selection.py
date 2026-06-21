import json
import tempfile
import unittest
from pathlib import Path

from core.st_utils.history_video import find_project_original_videos, is_generated_video


class HistoryOriginalVideoSelectionTest(unittest.TestCase):
    def test_versioned_subtitle_videos_are_generated(self):
        self.assertTrue(is_generated_video("movie_sub.mp4"))
        self.assertTrue(is_generated_video("movie_sub_v2.mp4"))
        self.assertTrue(is_generated_video("movie_trans_src_sub_v12.mp4"))
        self.assertTrue(is_generated_video("movie_dub_v3.mp4"))
        self.assertFalse(is_generated_video("movie.mp4"))

    def test_manifest_source_video_is_the_only_history_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            original = project / "Original video.webm"
            merged = project / "Original_video_trans_src_sub_v4.mp4"
            original.touch()
            merged.touch()
            (project / "manifest.json").write_text(
                json.dumps({"source_video": original.name}), encoding="utf-8"
            )

            videos = find_project_original_videos(project, (".mp4", ".webm"))

            self.assertEqual(videos, [str(original)])


if __name__ == "__main__":
    unittest.main()
