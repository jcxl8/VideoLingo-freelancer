import hashlib
import json
import os

from core.utils.config_utils import load_key
from core.utils.models import (
    _4_2_TRANSLATION,
    _4_3_AMBIGUITY,
    _5_REMERGED,
    _5_SPLIT_SUB,
)


MODEL_CACHE_NAME = ".translation_model_cache"
PROFILE_CACHE_NAME = ".translation_profile_cache"


def _safe_load_key(key, default=""):
    try:
        value = load_key(key)
    except Exception:
        return default
    return "" if value is None else value


def get_current_translation_model():
    """Return the visible translation model name from config."""
    model = str(_safe_load_key("translator_api.model")).strip()
    if model:
        return model
    return str(_safe_load_key("api.model")).strip()


def get_current_translation_profile_signature():
    """Return a stable signature for the active translation API profile."""
    profile = {
        "translator_api.key": str(_safe_load_key("translator_api.key")).strip(),
        "translator_api.base_url": str(_safe_load_key("translator_api.base_url")).strip(),
        "translator_api.model": str(_safe_load_key("translator_api.model")).strip(),
        "translator_api.llm_support_json": bool(_safe_load_key("translator_api.llm_support_json", False)),
        "translator_refine_with_workflow": bool(_safe_load_key("translator_refine_with_workflow", False)),
    }
    if not profile["translator_api.model"]:
        profile.update({
            "api.key": str(_safe_load_key("api.key")).strip(),
            "api.base_url": str(_safe_load_key("api.base_url")).strip(),
            "api.model": str(_safe_load_key("api.model")).strip(),
            "api.llm_support_json": bool(_safe_load_key("api.llm_support_json", False)),
        })
    payload = json.dumps(profile, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_translation_cache_paths():
    log_dir = os.path.dirname(_4_2_TRANSLATION)
    return {
        "model": os.path.join(log_dir, MODEL_CACHE_NAME),
        "profile": os.path.join(log_dir, PROFILE_CACHE_NAME),
    }


def read_last_translation_profile_signature():
    paths = get_translation_cache_paths()
    profile_cache = paths["profile"]
    if os.path.exists(profile_cache):
        try:
            with open(profile_cache, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""
    model_cache = paths["model"]
    if os.path.exists(model_cache):
        try:
            with open(model_cache, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""
    return ""


def write_translation_profile_cache():
    paths = get_translation_cache_paths()
    os.makedirs(os.path.dirname(paths["profile"]), exist_ok=True)
    with open(paths["model"], "w", encoding="utf-8") as f:
        f.write(get_current_translation_model())
    with open(paths["profile"], "w", encoding="utf-8") as f:
        f.write(get_current_translation_profile_signature())


def translation_profile_changed():
    if not os.path.exists(_4_2_TRANSLATION):
        return False
    cached = read_last_translation_profile_signature()
    current = get_current_translation_profile_signature()
    return bool(cached and current and cached != current)


def clean_retranslation_outputs(project_root="."):
    """Remove translation and subtitle downstream files without touching ASR/splitting outputs."""
    rel_paths = [
        _4_2_TRANSLATION,
        os.path.join(os.path.dirname(_4_2_TRANSLATION), MODEL_CACHE_NAME),
        os.path.join(os.path.dirname(_4_2_TRANSLATION), PROFILE_CACHE_NAME),
        _5_SPLIT_SUB,
        _5_REMERGED,
        _4_3_AMBIGUITY,
        "output/ambiguity_report.md",
        "output/log/subtitle_proofread_report.json",
        "output/subtitle_proofread_report.md",
        "output/audio/trans_subs_for_audio.srt",
    ]
    removed = []
    for rel_path in rel_paths:
        path = os.path.join(project_root, rel_path)
        if os.path.exists(path):
            os.remove(path)
            removed.append(rel_path)
    return removed
