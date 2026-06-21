import json
from functools import lru_cache

DISPLAY_LANGUAGES = {
    "🇬🇧 English": "en",
    "🇨🇳 简体中文": "zh-CN",
    "🇪🇸 Español": "es",
    "🇷🇺 Русский": "ru",
    "🇫🇷 Français": "fr",
    "🇩🇪 Deutsch": "de",
    "🇮🇹 Italiano": "it",
    "🇯🇵 日本語": "ja",
}

# Load the language file based on user selection
@lru_cache(maxsize=None)
def load_translations(language="en"):
    try:
        with open(f'translations/{language}.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}

# Function to fetch the translation
def translate(key):
    from core.utils.config_utils import load_key
    try:
        display_language = load_key("display_language")
    except Exception:
        display_language = "en"

    selected_catalog = load_translations(display_language)
    if key in selected_catalog:
        return selected_catalog[key]

    english_catalog = selected_catalog if display_language == "en" else load_translations("en")
    return english_catalog.get(key, key)
