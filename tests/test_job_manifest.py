import json
import os
import tempfile
import unittest
from pathlib import Path

from core.job_manifest import (
    load_job_manifest,
    manifest_input_video,
    record_subtitle_merge,
)


class JobManifestTest(unittest.TestCase):
    def test_records_merge_with_input_fingerprint_and_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "source.mp4"
            subtitle = root / "trans.srt"
            output = root / "merged.mp4"
            manifest = root / "job_manifest.json"
            video.write_bytes(b"video")
            subtitle.write_text("subtitle", encoding="utf-8")
            output.write_bytes(b"merged")

            saved = record_subtitle_merge(
                video_file=video,
                output_video=output,
                src_srt=None,
                trans_srt=subtitle,
                subtitle_mode="translation_only",
                manifest_path=manifest,
            )

            self.assertEqual(saved["status"], "completed")
            self.assertEqual(saved["stage"], "subtitle_merge")
            self.assertEqual(saved["input"]["path"], str(video.resolve()))
            self.assertEqual(saved["artifacts"]["video"], str(output.resolve()))
            self.assertEqual(load_job_manifest(manifest), saved)
            self.assertEqual(json.loads(manifest.read_text())["input"]["size"], 5)

            self.assertEqual(manifest_input_video(manifest), str(video.resolve()))
            video.write_bytes(b"changed video")
            self.assertIsNone(manifest_input_video(manifest))

    def test_corrupt_manifest_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "job_manifest.json"
            manifest.write_text("{broken", encoding="utf-8")
            self.assertIsNone(load_job_manifest(manifest))
            self.assertTrue(list(manifest.parent.glob("job_manifest.json.corrupt-*")))


if __name__ == "__main__":
    unittest.main()
