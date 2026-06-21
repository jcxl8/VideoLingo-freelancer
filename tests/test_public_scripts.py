from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicScriptsTest(unittest.TestCase):
    def test_local_translator_scripts_do_not_embed_user_paths(self):
        scripts = [
            ROOT / "scripts" / "start_hymt2_8765.sh",
            ROOT / "scripts" / "launch_hymt2_8765_once.sh",
        ]

        for script in scripts:
            text = script.read_text(encoding="utf-8")
            self.assertNotIn("/Users/", text, script.name)

    def test_translator_launcher_accepts_portable_overrides(self):
        text = (ROOT / "scripts" / "start_hymt2_8765.sh").read_text(encoding="utf-8")

        self.assertIn("LLAMA_SERVER", text)
        self.assertIn("HYMT2_MODEL", text)


if __name__ == "__main__":
    unittest.main()
