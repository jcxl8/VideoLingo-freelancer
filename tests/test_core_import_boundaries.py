import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CoreImportBoundariesTest(unittest.TestCase):
    def test_import_core_does_not_eagerly_load_pipeline_modules(self):
        code = (
            "import sys; import core; "
            "print(any(name.startswith('core._7_sub_into_vid') for name in sys.modules))"
        )

        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        )

        self.assertEqual(result.stdout.strip(), "False")

    def test_legacy_pipeline_import_still_resolves(self):
        from core import _7_sub_into_vid

        self.assertTrue(callable(_7_sub_into_vid.get_default_subtitle_paths))

    def test_subtitle_format_module_matches_legacy_helpers(self):
        from core import _7_sub_into_vid
        from core import subtitle_formats

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.srt"
            path.write_text(
                "1\n00:00:01,250 --> 00:00:02,500\nHello\n",
                encoding="utf-8",
            )

            self.assertEqual(
                subtitle_formats.read_srt_entries(path),
                _7_sub_into_vid._read_srt_entries(path),
            )
            self.assertEqual(
                subtitle_formats.ass_timestamp(61.25),
                _7_sub_into_vid._ass_timestamp(61.25),
            )


if __name__ == "__main__":
    unittest.main()
