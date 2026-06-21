from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "LOCAL_OPTIMIZATION_GUIDE.md"


class LocalOptimizationGuideTest(unittest.TestCase):
    def test_guide_covers_current_custom_architecture(self):
        text = GUIDE.read_text(encoding="utf-8")
        required = (
            "https://github.com/jcxl8/VideoLingo-freelancer.git",
            "core/asr_backend/mlx_whisper_local.py",
            "core/subtitle_layout.py",
            "core/subtitle_proofread.py",
            "core/st_utils/task_runner.py",
            "core/utils/secret_store.py",
            "core/utils/atomic_files.py",
            "scripts/check_tracked_secrets.py",
            "requirements-ci.txt",
            "python -m unittest discover -v tests",
        )
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_guide_keeps_machine_specific_data_out_of_migration(self):
        text = GUIDE.read_text(encoding="utf-8")
        for item in (
            ".streamlit/secrets.toml",
            "VIDEOLINGO_API_KEY",
            "output/",
            "history/",
            "_model_cache/",
        ):
            with self.subTest(item=item):
                self.assertIn(item, text)


if __name__ == "__main__":
    unittest.main()
