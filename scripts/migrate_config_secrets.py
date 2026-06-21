import argparse
import json
import os
import tempfile
from pathlib import Path

from ruamel.yaml import YAML

from core.utils.secret_store import (
    SECRET_PLACEHOLDERS,
    SENSITIVE_CONFIG_KEYS,
    write_secret_override,
)
from core.utils.atomic_files import atomic_write_json


KNOWN_PLACEHOLDER_VALUES = {
    "",
    "your-api-key",
    "YOUR_API_KEY",
    "YOUR_302_API_KEY",
    "YOUR_SF_KEY",
    "your_302_api_key",
    "your_elevenlabs_api_key",
    "sk-local",
}


def _get_nested(data, dotted_key):
    value = data
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _set_nested(data, dotted_key, new_value):
    current = data
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    if not isinstance(current, dict) or parts[-1] not in current:
        return False
    current[parts[-1]] = new_value
    return True


def _atomic_yaml_write(path, data, yaml):
    path = Path(path)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=str(path.parent), text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            yaml.dump(data, file)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.remove(temporary_name)


def _scrub_history(path):
    path = Path(path)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(data, dict):
        return
    changed = False
    for key in SENSITIVE_CONFIG_KEYS:
        if key in data:
            data.pop(key, None)
            changed = True
    if changed:
        atomic_write_json(path, data, indent=2)


def migrate_config_secrets(
    config_path="config.yaml",
    secrets_path=".streamlit/secrets.toml",
    history_path="config_history.json",
):
    config_path = Path(config_path)
    yaml = YAML()
    yaml.preserve_quotes = True
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.load(file)

    migrated = []
    for key in SENSITIVE_CONFIG_KEYS:
        value = _get_nested(config, key)
        if value is None or str(value).strip() in KNOWN_PLACEHOLDER_VALUES:
            continue
        write_secret_override(key, value, path=secrets_path)
        _set_nested(config, key, SECRET_PLACEHOLDERS[key])
        migrated.append(key)

    if migrated:
        _atomic_yaml_write(config_path, config, yaml)
    _scrub_history(history_path)
    for key in migrated:
        print(f"Migrated sensitive configuration: {key}")
    return migrated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--secrets", default=".streamlit/secrets.toml")
    parser.add_argument("--history", default="config_history.json")
    args = parser.parse_args()
    migrate_config_secrets(args.config, args.secrets, args.history)


if __name__ == "__main__":
    main()
