import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class SecretConfigTest(unittest.TestCase):
    def test_environment_precedes_toml_and_yaml(self):
        from core.utils.secret_store import resolve_secret_override

        value = resolve_secret_override(
            "api.key",
            "yaml-secret",
            environ={"VIDEOLINGO_API_KEY": "env-secret"},
            secrets={"VIDEOLINGO_API_KEY": "toml-secret"},
        )

        self.assertEqual(value, "env-secret")

    def test_toml_precedes_yaml(self):
        from core.utils.secret_store import resolve_secret_override

        value = resolve_secret_override(
            "translator_api.key",
            "yaml-secret",
            environ={},
            secrets={"VIDEOLINGO_TRANSLATOR_API_KEY": "toml-secret"},
        )

        self.assertEqual(value, "toml-secret")

    def test_cookie_path_uses_mapped_secret(self):
        from core.utils.secret_store import resolve_secret_override

        value = resolve_secret_override(
            "youtube.cookies_path",
            "",
            environ={},
            secrets={"VIDEOLINGO_YOUTUBE_COOKIES_PATH": "/private/cookies.txt"},
        )

        self.assertEqual(value, "/private/cookies.txt")

    def test_non_sensitive_key_keeps_yaml_value(self):
        from core.utils.secret_store import resolve_secret_override

        self.assertEqual(
            resolve_secret_override(
                "subtitle.max_length",
                100,
                environ={"subtitle.max_length": "200"},
                secrets={"subtitle.max_length": 300},
            ),
            100,
        )

    def test_all_supported_service_credentials_are_sensitive(self):
        from core.utils.secret_store import SENSITIVE_CONFIG_KEYS

        expected = {
            "api.key",
            "translator_api.key",
            "youtube.cookies_path",
            "whisper.whisperX_302_api_key",
            "whisper.elevenlabs_api_key",
            "sf_fish_tts.api_key",
            "openai_tts.api_key",
            "azure_tts.api_key",
            "fish_tts.api_key",
            "sf_cosyvoice2.api_key",
            "f5tts.302_api",
        }

        self.assertTrue(expected.issubset(SENSITIVE_CONFIG_KEYS))

    def test_secret_write_preserves_unrelated_entries(self):
        from core.utils.secret_store import load_local_secrets, write_secret_override

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "secrets.toml"
            path.write_text('UNRELATED = "keep-me"\nVIDEOLINGO_API_KEY = "old"\n', encoding="utf-8")

            result = write_secret_override("api.key", "new-secret", path=path)
            content = path.read_text(encoding="utf-8")
            parsed = load_local_secrets(path)
            mode = stat.S_IMODE(path.stat().st_mode)

        self.assertEqual(result, "VIDEOLINGO_API_KEY")
        self.assertNotIn("new-secret", result)
        self.assertIn('UNRELATED = "keep-me"', content)
        self.assertEqual(parsed["VIDEOLINGO_API_KEY"], "new-secret")
        self.assertEqual(mode, 0o600)

    def test_load_key_uses_secret_override(self):
        from core.utils import config_utils

        with patch.object(
            config_utils,
            "resolve_secret_override",
            side_effect=lambda key, value: "overridden" if key == "api.key" else value,
        ):
            self.assertEqual(config_utils.load_key("api.key"), "overridden")

    def test_sensitive_history_is_not_recorded(self):
        from core.utils import config_utils

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            config_utils, "CONFIG_HISTORY_PATH", os.path.join(tmpdir, "history.json")
        ):
            config_utils.record_key_history("api.key", "must-not-be-written")

            self.assertFalse(os.path.exists(config_utils.CONFIG_HISTORY_PATH))

    def test_failed_atomic_config_replace_keeps_previous_yaml(self):
        from core.utils import config_utils

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("subtitle:\n  max_length: 75\n", encoding="utf-8")
            with patch.object(config_utils, "CONFIG_PATH", str(config_path)), patch.object(
                config_utils, "atomic_write_text", side_effect=RuntimeError("replace failed"), create=True
            ):
                config_utils._invalidate_config_cache()
                with self.assertRaisesRegex(RuntimeError, "replace failed"):
                    config_utils.update_key("subtitle.max_length", 100)
                config_utils._invalidate_config_cache()
                self.assertEqual(config_utils.load_key("subtitle.max_length"), 75)


if __name__ == "__main__":
    unittest.main()
