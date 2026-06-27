from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GithubStarButtonTest(unittest.TestCase):
    def test_streamlit_star_button_links_to_freelancer_repository(self):
        source = (ROOT / "core" / "st_utils" / "imports_and_utils.py").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'href="https://github.com/jcxl8/VideoLingo-freelancer"',
            source,
        )
        self.assertNotIn(
            'href="https://github.com/Huanshere/VideoLingo"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
