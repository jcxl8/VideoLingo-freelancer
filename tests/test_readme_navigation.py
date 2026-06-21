from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReadmeNavigationTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
