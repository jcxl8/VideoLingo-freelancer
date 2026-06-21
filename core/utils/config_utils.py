from ruamel.yaml import YAML
from io import StringIO
import threading
import json
import os
import time

from core.utils.secret_store import (
    is_sensitive_config_key,
    resolve_secret_override,
    write_secret_override,
)
from core.utils.atomic_files import atomic_write_json, atomic_write_text

CONFIG_PATH = 'config.yaml'
CONFIG_HISTORY_PATH = 'config_history.json'
lock = threading.RLock()
_config_cache = None
_config_cache_mtime = None

yaml = YAML()
yaml.preserve_quotes = True

def _read_config_unlocked(force=False):
    global _config_cache, _config_cache_mtime
    mtime = os.path.getmtime(CONFIG_PATH)
    if not force and _config_cache is not None and _config_cache_mtime == mtime:
        return _config_cache
    with open(CONFIG_PATH, 'r', encoding='utf-8') as file:
        _config_cache = yaml.load(file)
    _config_cache_mtime = mtime
    return _config_cache

def _invalidate_config_cache():
    global _config_cache, _config_cache_mtime
    _config_cache = None
    _config_cache_mtime = None

def _serialize_history_value(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)

def _load_config_history_unlocked():
    if not os.path.exists(CONFIG_HISTORY_PATH):
        return {}
    try:
        with open(CONFIG_HISTORY_PATH, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _save_config_history_unlocked(data):
    atomic_write_json(CONFIG_HISTORY_PATH, data, indent=2)

def record_key_history(key, value, limit=12):
    if is_sensitive_config_key(key):
        return
    value_text = _serialize_history_value(value).strip()
    if not value_text:
        return
    with lock:
        data = _load_config_history_unlocked()
        values = [item for item in data.get(key, []) if item.get("value") != value_text]
        values.insert(0, {"value": value_text, "updated_at": time.time()})
        data[key] = values[:limit]
        _save_config_history_unlocked(data)

def get_key_history(key):
    with lock:
        data = _load_config_history_unlocked()
    values = []
    for item in data.get(key, []):
        if isinstance(item, dict) and item.get("value") not in values:
            values.append(item.get("value"))
    return values

def remove_key_history(key, value):
    value_text = _serialize_history_value(value).strip()
    with lock:
        data = _load_config_history_unlocked()
        data[key] = [
            item for item in data.get(key, [])
            if isinstance(item, dict) and item.get("value") != value_text
        ]
        _save_config_history_unlocked(data)

def load_history_metadata(key, default=None):
    with lock:
        data = _load_config_history_unlocked()
    value = data.get(key, default)
    return value if value is not None else default

def save_history_metadata(key, value):
    with lock:
        data = _load_config_history_unlocked()
        data[key] = value
        _save_config_history_unlocked(data)

# -----------------------
# load & update config
# -----------------------

def load_key(key):
    with lock:
        data = _read_config_unlocked()

    keys = key.split('.')
    value = data
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            raise KeyError(f"Key '{k}' not found in configuration")
    return resolve_secret_override(key, value)


def is_local_translator():
    """Detect if translator_api points to a local (single-threaded) model."""
    try:
        base_url = str(load_key("translator_api.base_url") or "").lower()
        key = str(load_key("translator_api.key") or "").lower()
        if "127.0.0.1" in base_url or "localhost" in base_url:
            return True
        if key in ("sk-local", "local", "none", ""):
            return True
    except KeyError:
        pass
    return False


def is_remote_translator():
    """Detect if translator_api points to a remote LLM (not a local model)."""
    try:
        model = str(load_key("translator_api.model") or "").strip()
        if not model:
            return False
        base_url = str(load_key("translator_api.base_url") or "").lower()
        key = str(load_key("translator_api.key") or "").lower()
        # Local models use localhost or sk-local
        if "127.0.0.1" in base_url or "localhost" in base_url:
            return False
        if key in ("sk-local", "local", "none", ""):
            return False
        return True
    except KeyError:
        return False


def get_effective_max_workers():
    """Return translation concurrency: 1 for local translator, else configured translation_max_workers."""
    try:
        configured = load_key("translation_max_workers")
    except KeyError:
        configured = load_key("max_workers")
    if is_local_translator():
        return 1
    return configured

def update_key(key, new_value):
    with lock:
        data = _read_config_unlocked(force=True)

        keys = key.split('.')
        current = data
        for k in keys[:-1]:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return False

        if isinstance(current, dict) and keys[-1] in current:
            if is_sensitive_config_key(key):
                write_secret_override(key, new_value)
                _invalidate_config_cache()
                return True
            record_key_history(key, current[keys[-1]])
            current[keys[-1]] = new_value
            output = StringIO()
            yaml.dump(data, output)
            atomic_write_text(CONFIG_PATH, output.getvalue(), mode=0o644)
            _invalidate_config_cache()
            record_key_history(key, new_value)
            return True
        else:
            raise KeyError(f"Key '{keys[-1]}' not found in configuration")
        
# basic utils
def get_joiner(language):
    if language in load_key('language_split_with_space'):
        return " "
    elif language in load_key('language_split_without_space'):
        return ""
    else:
        print(f"⚠️ Unsupported language code '{language}', using space joiner fallback.")
        return " "

if __name__ == "__main__":
    print(load_key('language_split_with_space'))
