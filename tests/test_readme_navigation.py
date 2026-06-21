from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOCALIZED_PAGES = ("zh", "es", "ru", "fr", "de", "it", "ja")


class ReadmeNavigationTest(unittest.TestCase):
    def test_root_readme_documents_project_structure(self):
        text = ROOT.joinpath("README.md").read_text(encoding="utf-8")
        start = text.index("## 🗂️ Project Structure")
        end = text.index("\n## ", start + 4)
        section = text[start:end]

        required = (
            "VideoLingo-freelancer/",
            "st.py",
            "setup_env.py",
            "install.py",
            "core/",
            "asr_backend/",
            "tts_backend/",
            "st_utils/",
            "scripts/",
            "tests/",
            "translations/",
            "docs/",
            "batch/",
            "output/",
            "history/",
            "_model_cache/",
        )
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, section)
        self.assertNotIn("config_history.json", section)
        self.assertLess(text.index("## ⚙️ Configuration"), start)
        self.assertLess(start, text.index("## ✅ Validation"))

    def test_root_readme_recommends_tested_local_translation_model(self):
        text = ROOT.joinpath("README.md").read_text(encoding="utf-8")
        required = (
            "Local Translation Model",
            "https://huggingface.co/tencent/Hy-MT2-7B",
            "Mac mini M4",
            "32 GB",
            "33 languages",
            "OpenAI-compatible",
            "translator_api:",
            "model: hy-mt2-7b",
        )
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_all_readmes_document_uv_python_and_ffmpeg_installation(self):
        pages = [ROOT / "README.md"] + [
            ROOT / "translations" / f"README.{code}.md"
            for code in LOCALIZED_PAGES
        ]
        required = (
            "python setup_env.py",
            "Python 3.12",
            "FFmpeg",
            "python install.py",
        )

        for page in pages:
            text = page.read_text(encoding="utf-8")
            for item in required:
                with self.subTest(page=page.name, item=item):
                    self.assertIn(item, text)

    def test_all_readmes_publish_agent_skill_entry(self):
        pages = [ROOT / "README.md"] + [
            ROOT / "translations" / f"README.{code}.md"
            for code in LOCALIZED_PAGES
        ]
        required = (
            "https://github.com/jcxl8/videolingo-freelancer-skill",
            "Codex",
            "Claude Code",
            "OpenClaw",
            "CLI",
        )

        for page in pages:
            text = page.read_text(encoding="utf-8")
            for item in required:
                with self.subTest(page=page.name, item=item):
                    self.assertIn(item, text)

    def test_root_readme_has_upstream_inspired_sections(self):
        text = ROOT.joinpath("README.md").read_text(encoding="utf-8")

        for heading in (
            "Overview",
            "Key Features",
            "Interface Languages",
            "Installation",
            "Configuration",
            "Current Limitations",
            "License",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, text)
        self.assertIn("Huanshere/VideoLingo", text)
        self.assertNotIn("gpt302.saaslink.net", text)
        self.assertNotIn("share.fastgpt.in", text)

    def test_localized_navigation_targets_exist_and_are_branded(self):
        for code in LOCALIZED_PAGES:
            with self.subTest(code=code):
                page = ROOT / "translations" / f"README.{code}.md"
                self.assertTrue(page.is_file(), code)
                text = page.read_text(encoding="utf-8")
                self.assertIn("VideoLingo-Freelancer", text)
                self.assertIn("../README.md", text)
                self.assertIn(
                    "https://github.com/jcxl8/VideoLingo-freelancer.git",
                    text,
                )


if __name__ == "__main__":
    unittest.main()
