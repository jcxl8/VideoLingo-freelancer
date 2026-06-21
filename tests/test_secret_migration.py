import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ruamel.yaml import YAML


class SecretMigrationTest(unittest.TestCase):
    def test_migration_moves_values_scrubs_yaml_and_history_without_leaking(self):
        from scripts.migrate_config_secrets import migrate_config_secrets

        yaml = YAML()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "config.yaml"
            secrets_path = root / ".streamlit" / "secrets.toml"
            history_path = root / "config_history.json"
            config_path.write_text(
                "api:\n  key: top-secret-api\n"
                "translator_api:\n  key: sk-local\n"
                "youtube:\n  cookies_path: /private/cookies.txt\n",
                encoding="utf-8",
            )
            history_path.write_text(
                json.dumps(
                    {
                        "api.key": [{"value": "top-secret-api"}],
                        "target_language": [{"value": "简体中文"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                migrated = migrate_config_secrets(
                    config_path=config_path,
                    secrets_path=secrets_path,
                    history_path=history_path,
                )
            with config_path.open("r", encoding="utf-8") as file:
                config = yaml.load(file)
            history = json.loads(history_path.read_text(encoding="utf-8"))
            secrets_text = secrets_path.read_text(encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                migrated_again = migrate_config_secrets(
                    config_path=config_path,
                    secrets_path=secrets_path,
                    history_path=history_path,
                )

        self.assertEqual(
            migrated,
            ["api.key", "youtube.cookies_path"],
        )
        self.assertEqual(migrated_again, [])
        self.assertEqual(config["api"]["key"], "YOUR_API_KEY")
        self.assertEqual(config["translator_api"]["key"], "sk-local")
        self.assertEqual(config["youtube"]["cookies_path"], "")
        self.assertNotIn("api.key", history)
        self.assertIn("target_language", history)
        self.assertIn("VIDEOLINGO_API_KEY", secrets_text)
        self.assertNotIn("top-secret-api", output.getvalue())
        self.assertNotIn("/private/cookies.txt", output.getvalue())


if __name__ == "__main__":
    unittest.main()
