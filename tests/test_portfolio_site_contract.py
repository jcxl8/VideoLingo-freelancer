from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PortfolioSiteContractTest(unittest.TestCase):
    def test_english_portfolio_page_exists_and_loads_component(self):
        page = ROOT / "docs" / "pages" / "index.en-US.mdx"
        self.assertTrue(page.is_file())
        text = page.read_text(encoding="utf-8")
        self.assertIn("PortfolioPage", text)
        self.assertIn("portfolioContent", text)

    def test_chinese_supporting_page_exists(self):
        page = ROOT / "docs" / "pages" / "index.zh-CN.mdx"
        self.assertTrue(page.is_file())
        text = page.read_text(encoding="utf-8")
        self.assertIn("VideoLingo-Freelancer", text)
        self.assertIn("英文主站", text)
        self.assertIn("/en-US", text)

    def test_portfolio_content_matches_approved_positioning(self):
        content = ROOT / "docs" / "lib" / "portfolio-content.ts"
        self.assertTrue(content.is_file())
        text = content.read_text(encoding="utf-8")
        required = (
            "Turn your videos into publish-ready multilingual content",
            "Request a Quote",
            "View Work Samples",
            "Subtitle Translation",
            "Hard-Sub Video Rendering",
            "Bilingual Subtitle Review",
            "AI-Assisted Dubbing",
            "Vertical Video Localization",
            "VideoLingo-Freelancer",
            "MLX Whisper",
            "Hy-MT2-7B",
            "https://github.com/jcxl8/VideoLingo-freelancer",
            "https://github.com/jcxl8/videolingo-freelancer-skill",
        )
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_portfolio_component_contains_required_sections(self):
        component = ROOT / "docs" / "components" / "portfolio" / "portfolio-page.tsx"
        self.assertTrue(component.is_file())
        text = component.read_text(encoding="utf-8")
        required = (
            'id="services"',
            'id="portfolio"',
            'id="workflow"',
            'id="local-ai-stack"',
            'id="about"',
            'id="contact"',
            "sourceLanguage",
            "targetLanguage",
            "turnaround",
        )
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_readme_links_portfolio_site(self):
        readme = ROOT / "README.md"
        text = readme.read_text(encoding="utf-8")
        self.assertIn("Personal Portfolio Website", text)
        self.assertIn("docs/pages/index.en-US.mdx", text)


if __name__ == "__main__":
    unittest.main()
