import tempfile
import unittest
from pathlib import Path

from core.st_utils.subtitle_preview_cache import ensure_preview


class SubtitlePreviewCacheTest(unittest.TestCase):
    def test_existing_preview_skips_renderer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preview.jpg"
            path.write_bytes(b"cached")
            calls = []

            generated = ensure_preview(path, lambda: calls.append("render"))

            self.assertFalse(generated)
            self.assertEqual(calls, [])

    def test_missing_preview_runs_renderer_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preview.jpg"
            calls = []

            def render():
                calls.append("render")
                path.write_bytes(b"new")

            self.assertTrue(ensure_preview(path, render))
            self.assertFalse(ensure_preview(path, render))
            self.assertEqual(calls, ["render"])

    def test_changed_cache_path_runs_renderer(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            for name in ("mode-a.jpg", "mode-b.jpg"):
                path = Path(tmp) / name

                def render(path=path):
                    calls.append(path.name)
                    path.write_bytes(b"new")

                self.assertTrue(ensure_preview(path, render))

            self.assertEqual(calls, ["mode-a.jpg", "mode-b.jpg"])


if __name__ == "__main__":
    unittest.main()
