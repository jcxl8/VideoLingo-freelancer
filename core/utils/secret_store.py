import json
import os
import re
import tempfile
import tomllib
from pathlib import Path


DEFAULT_SECRETS_PATH = Path(".streamlit/secrets.toml")
SENSITIVE_CONFIG_KEYS = {
    "api.key": "VIDEOLINGO_API_KEY",
    "translator_api.key": "VIDEOLINGO_TRANSLATOR_API_KEY",
    "youtube.cookies_path": "VIDEOLINGO_YOUTUBE_COOKIES_PATH",
    "whisper.whisperX_302_api_key": "VIDEOLINGO_WHISPERX_302_API_KEY",
    "whisper.elevenlabs_api_key": "VIDEOLINGO_ELEVENLABS_API_KEY",
    "sf_fish_tts.api_key": "VIDEOLINGO_SF_FISH_TTS_API_KEY",
    "openai_tts.api_key": "VIDEOLINGO_OPENAI_TTS_API_KEY",
    "azure_tts.api_key": "VIDEOLINGO_AZURE_TTS_API_KEY",
    "fish_tts.api_key": "VIDEOLINGO_FISH_TTS_API_KEY",
    "sf_cosyvoice2.api_key": "VIDEOLINGO_SF_COSYVOICE2_API_KEY",
    "f5tts.302_api": "VIDEOLINGO_F5TTS_302_API_KEY",
}

SECRET_PLACEHOLDERS = {
    "api.key": "YOUR_API_KEY",
    "translator_api.key": "sk-local",
    "youtube.cookies_path": "",
    "whisper.whisperX_302_api_key": "your_302_api_key",
    "whisper.elevenlabs_api_key": "your_elevenlabs_api_key",
    "sf_fish_tts.api_key": "YOUR_API_KEY",
    "openai_tts.api_key": "YOUR_302_API_KEY",
    "azure_tts.api_key": "YOUR_302_API_KEY",
    "fish_tts.api_key": "YOUR_302_API_KEY",
    "sf_cosyvoice2.api_key": "YOUR_SF_KEY",
    "f5tts.302_api": "YOUR_302_API_KEY",
}


def is_sensitive_config_key(key):
    return key in SENSITIVE_CONFIG_KEYS


def load_local_secrets(path=DEFAULT_SECRETS_PATH):
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid local secrets file: {path}") from exc
    return data if isinstance(data, dict) else {}


def resolve_secret_override(key, yaml_value, environ=None, secrets=None):
    env_name = SENSITIVE_CONFIG_KEYS.get(key)
    if not env_name:
        return yaml_value
    environment = os.environ if environ is None else environ
    env_value = environment.get(env_name)
    if env_value not in (None, ""):
        return env_value
    secret_values = load_local_secrets() if secrets is None else secrets
    secret_value = secret_values.get(env_name)
    return secret_value if secret_value not in (None, "") else yaml_value


def write_secret_override(key, value, path=DEFAULT_SECRETS_PATH):
    env_name = SENSITIVE_CONFIG_KEYS.get(key)
    if not env_name:
        raise KeyError(f"Configuration key is not registered as sensitive: {key}")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    assignment = f"{env_name} = {json.dumps(str(value), ensure_ascii=False)}"
    pattern = re.compile(rf"^\s*{re.escape(env_name)}\s*=.*$", re.MULTILINE)
    if pattern.search(existing):
        updated = pattern.sub(assignment, existing, count=1)
    else:
        separator = "" if not existing or existing.endswith("\n") else "\n"
        updated = f"{existing}{separator}{assignment}\n"

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as file:
            file.write(updated)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(temporary_name):
            os.remove(temporary_name)
    return env_name
