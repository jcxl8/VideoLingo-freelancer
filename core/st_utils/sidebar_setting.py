import uuid
import streamlit as st
import time
import os
import shutil
from translations.translations import translate as t
from translations.translations import DISPLAY_LANGUAGES
from core import _7_sub_into_vid
from core.utils import *

ASR_LANGUAGE_OPTIONS = [
    ("🌐 自动检测", "auto", None),
    ("🇺🇸 English", "en", "English"),
    ("🇨🇳 简体中文", "zh", "简体中文"),
    ("🇪🇸 Español", "es", "西班牙语"),
    ("🇷🇺 Русский", "ru", "俄语"),
    ("🇫🇷 Français", "fr", "法语"),
    ("🇩🇪 Deutsch", "de", "德语"),
    ("🇮🇹 Italiano", "it", "意大利语"),
    ("🇯🇵 日本語", "ja", "日语"),
    ("🇰🇷 한국어", "ko", "韩语"),
]

TARGET_LANGUAGE_OPTIONS = [
    ("🇺🇸 English", "English"),
    ("🇨🇳 简体中文", "简体中文"),
    ("🇪🇸 Español", "西班牙语"),
    ("🇯🇵 日本語", "日语"),
    ("🇰🇷 한국어", "韩语"),
    ("🇩🇪 Deutsch", "德语"),
    ("🇷🇺 Русский", "俄语"),
    ("🇵🇹 Português", "葡萄牙语"),
]
MANUAL_LANGUAGE_LABEL = "✍️ 手动输入"
MANUAL_LANGUAGE_VALUE = "__manual__"


def _normalize_asr_language(value):
    value = str(value or "").strip()
    return value or "auto"

def _widget_key(config_key, suffix):
    return f"config_{config_key.replace('.', '_')}_{suffix}"

def _mask_secret(value):
    value = str(value or "")
    if len(value) <= 8:
        return value
    return f"{value[:4]}...{value[-4:]}"

def _format_history_display(value, history_format_func=None):
    """Format a history value for display."""
    if value == t("Custom..."):
        return f"✏️ {value}"
    return history_format_func(value) if history_format_func else str(value)

def config_input(label, key, help=None, history_format_func=None, on_history_select=None):
    """Config input with integrated history dropdown and inline delete buttons."""
    current_value = str(load_key(key))
    history = [item for item in get_key_history(key) if item and item != current_value]

    if not history:
        val = st.text_input(label, value=current_value, help=help, key=_widget_key(key, "input"))
        if val != current_value:
            if on_history_select and on_history_select(val):
                st.rerun()
            update_key(key, val)
            st.rerun()
        return current_value

    # Dropdown: current ✓ + history + Custom...
    options = [current_value] + history + [t("Custom...")]
    display_map = {}
    for v in options:
        if v == current_value:
            display_map[v] = f"{_format_history_display(v, history_format_func)} ✓"
        else:
            display_map[v] = _format_history_display(v, history_format_func)

    selected = st.selectbox(
        label,
        options=options,
        format_func=lambda v: display_map[v],
        help=help,
        key=_widget_key(key, "select"),
    )

    if selected == t("Custom..."):
        custom = st.text_input(
            f"{label}",
            value=current_value,
            help=help,
            key=_widget_key(key, "custom_input"),
            label_visibility="collapsed",
        )
        if custom and custom != current_value:
            if on_history_select and on_history_select(custom):
                st.rerun()
            update_key(key, custom)
            st.rerun()
    elif selected != current_value:
        if on_history_select and on_history_select(selected):
            st.rerun()
        update_key(key, selected)
        st.rerun()

    # Delete buttons for each history entry
    for h in history:
        c1, c2 = st.columns([12, 1])
        with c1:
            st.caption(_format_history_display(h, history_format_func))
        with c2:
            if st.button("✕", key=_widget_key(key, f"del_{h}"), help=t("delete_history_entry")):
                remove_key_history(key, h)
                st.rerun()

    return current_value

def config_select_with_history(label, key, options, values, help=None, history_format_func=None):
    """Select with predefined options and integrated history dropdown."""
    current_value = load_key(key)
    option_labels = list(options)
    option_values = list(values)

    if current_value not in option_values:
        option_labels = [str(current_value)] + option_labels
        option_values = [current_value] + option_values

    current_index = option_values.index(current_value)
    selected_label = st.selectbox(
        label,
        options=option_labels,
        index=current_index,
        help=help,
        key=_widget_key(key, "select"),
    )
    selected_value = option_values[option_labels.index(selected_label)]
    if selected_value != current_value:
        update_key(key, selected_value)
        st.rerun()
    return selected_value

def _api_prefix(api_role):
    return "translator_api" if api_role == "translator" else "api"

def _load_api_profiles(api_role):
    profiles = load_history_metadata("api_profiles", {})
    if not isinstance(profiles, dict):
        return {}
    role_profiles = profiles.get(api_role, {})
    return role_profiles if isinstance(role_profiles, dict) else {}

def _save_api_profiles(api_role, role_profiles):
    profiles = load_history_metadata("api_profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}
    profiles[api_role] = role_profiles
    save_history_metadata("api_profiles", profiles)

def _save_current_api_profile(api_role):
    prefix = _api_prefix(api_role)
    api_key = str(load_key(f"{prefix}.key")).strip()
    if not api_key:
        return False
    base_url = str(load_key(f"{prefix}.base_url"))
    model = str(load_key(f"{prefix}.model"))
    role_profiles = _load_api_profiles(api_role)
    # Deduplicate: if exact same (api_key, base_url, model) exists, update it
    existing_id = None
    for pid, p in role_profiles.items():
        if (p.get("api_key", pid) == api_key and
            p.get("base_url", "") == base_url and
            p.get("model", "") == model):
            existing_id = pid
            break
    if existing_id:
        profile_id = existing_id
    else:
        profile_id = uuid.uuid4().hex[:8]
    profile = {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "llm_support_json": bool(load_key(f"{prefix}.llm_support_json")),
        "updated_at": time.time(),
    }
    role_profiles[profile_id] = profile
    _save_api_profiles(api_role, role_profiles)
    record_key_history(f"{prefix}.key", api_key)
    record_key_history(f"{prefix}.base_url", base_url)
    record_key_history(f"{prefix}.model", model)
    return True

def _apply_api_profile(api_role, profile_id, profile):
    prefix = _api_prefix(api_role)
    api_key = profile.get("api_key", "")
    changed = False
    desired_values = {
        f"{prefix}.key": api_key,
        f"{prefix}.base_url": profile.get("base_url", ""),
        f"{prefix}.model": profile.get("model", ""),
        f"{prefix}.llm_support_json": bool(profile.get("llm_support_json", False)),
    }
    for key, value in desired_values.items():
        if value != "" and load_key(key) != value:
            update_key(key, value)
            changed = True
    return changed

def _apply_api_profile_from_key(api_role, api_key):
    role_profiles = _load_api_profiles(api_role)
    # Find profile by api_key (supports both old and new format)
    profile_id, profile = None, None
    for pid, p in role_profiles.items():
        p_api_key = p.get("api_key", pid)  # old format: key IS api_key
        if p_api_key == api_key:
            profile_id, profile = pid, p
            break
    if not profile:
        return False
    changed = _apply_api_profile(api_role, profile_id, profile)
    st.session_state[f"{api_role}_auto_test_pending"] = True
    st.toast(t("API profile loaded"), icon="✅")
    return changed or True

def _format_api_profile(profile_id, profile):
    api_key = profile.get("api_key", profile_id)
    base_url = profile.get("base_url", "")
    model = profile.get("model", "")
    parts = [_mask_secret(api_key)]
    if base_url:
        parts.append(base_url)
    if model:
        parts.append(model)
    return " | ".join(parts)

def _render_api_profile_manager(api_role):
    role_profiles = _load_api_profiles(api_role)
    options = sorted(
        role_profiles.keys(),
        key=lambda key: role_profiles.get(key, {}).get("updated_at", 0),
        reverse=True,
    )

    st.caption(t("API Profile"))
    if options:
        st.caption(t("Saved API profiles"))
        for profile_id in options:
            profile = role_profiles[profile_id]
            label = _format_api_profile(profile_id, profile)
            c1, c2 = st.columns([12, 1])
            with c1:
                if st.button(label, key=f"{api_role}_profile_{profile_id}", width="stretch",
                             help=t("Click to load this API profile")):
                    if _apply_api_profile(api_role, profile_id, profile):
                        st.session_state[f"{api_role}_auto_test_pending"] = True
                        st.toast(t("API profile loaded"), icon="✅")
                        st.rerun()
            with c2:
                if st.button("✕", key=f"{api_role}_profile_del_{profile_id}", help=t("Delete this profile")):
                    role_profiles.pop(profile_id, None)
                    _save_api_profiles(api_role, role_profiles)
                    st.toast(t("Deleted API profile"), icon="✅")
                    st.rerun()

    if st.button(t("Save Current API Profile"), key=f"{api_role}_api_profile_save"):
        if _save_current_api_profile(api_role):
            st.toast(t("Saved API profile"), icon="✅")
            st.rerun()
        else:
            st.toast(t("API key is empty"), icon="⚠️")

def _run_api_check(api_role):
    api_valid = check_api(api_role)
    role_name = t("Translation Model") if api_role == "translator" else t("Workflow Model")
    status_text = t("API Key is valid") if api_valid else t("API Key is invalid")
    st.toast(f"{role_name}{status_text}", icon="✅" if api_valid else "❌")
    return api_valid

def _run_pending_auto_api_check(api_role):
    pending_key = f"{api_role}_auto_test_pending"
    if st.session_state.pop(pending_key, False):
        with st.spinner(t("Testing connection automatically...")):
            _run_api_check(api_role)

def _seed_api_profiles_once():
    st.session_state["api_profiles_seeded"] = True

# ── Subtitle language pair profiles ──────────────────────
def _load_lang_profiles():
    profiles = load_history_metadata("lang_profiles", {})
    return profiles if isinstance(profiles, dict) else {}

def _save_lang_profiles(profiles):
    save_history_metadata("lang_profiles", profiles)

def _format_lang_profile(profile_id, profile):
    source = profile.get("source_lang", "")
    target = profile.get("target_lang", "")
    # Build lookup: code -> name without flag
    code_to_name = {}
    for flag_label, code, _ in ASR_LANGUAGE_OPTIONS:
        clean = flag_label.split(" ", 1)[-1] if " " in flag_label else flag_label
        code_to_name[code] = clean
    name_to_label = {
        target: label.split(" ", 1)[-1] if " " in label else label
        for label, target in TARGET_LANGUAGE_OPTIONS
    }
    source_label = code_to_name.get(source, source)
    target_label = name_to_label.get(target, target)
    return f"{source_label} → {target_label}"

def _save_current_lang_profile():
    source_lang = str(load_key("whisper.language"))
    target_lang = str(load_key("target_language"))
    if not source_lang or not target_lang:
        return False
    profiles = _load_lang_profiles()
    # Dedup
    existing_id = None
    for pid, p in profiles.items():
        if p.get("source_lang", "") == source_lang and p.get("target_lang", "") == target_lang:
            existing_id = pid
            break
    profile_id = existing_id if existing_id else uuid.uuid4().hex[:8]
    profiles[profile_id] = {
        "source_lang": source_lang,
        "target_lang": target_lang,
        "updated_at": time.time(),
    }
    _save_lang_profiles(profiles)
    return True

def _apply_lang_profile(profile_id, profile):
    changed = False
    for key, val in [("whisper.language", profile.get("source_lang", "")),
                     ("target_language", profile.get("target_lang", ""))]:
        if val and load_key(key) != val:
            update_key(key, val)
            changed = True
    return changed

def _render_lang_profile_manager():
    profiles = _load_lang_profiles()
    options = sorted(
        profiles.keys(),
        key=lambda k: profiles.get(k, {}).get("updated_at", 0),
        reverse=True,
    )
    st.caption(t("Saved Language Pairs"))
    if options:
        for profile_id in options:
            profile = profiles[profile_id]
            label = _format_lang_profile(profile_id, profile)
            c1, c2 = st.columns([12, 1])
            with c1:
                if st.button(label, key=f"lang_profile_{profile_id}", width="stretch",
                             help=t("Click to load this language pair")):
                    if _apply_lang_profile(profile_id, profile):
                        st.toast(t("Language pair loaded"), icon="✅")
                        st.rerun()
            with c2:
                if st.button("✕", key=f"lang_profile_del_{profile_id}", help=t("Delete")):
                    profiles.pop(profile_id, None)
                    _save_lang_profiles(profiles)
                    st.toast(t("Deleted"), icon="✅")
                    st.rerun()
    if st.button(t("Save Current Language Pair"), key="lang_profile_save"):
        if _save_current_lang_profile():
            st.toast(t("Saved language pair"), icon="✅")
            st.rerun()
        else:
            st.toast(t("Language pair incomplete"), icon="⚠️")

def _format_source_language(value):
    language_by_code = {code: label for label, code, _ in ASR_LANGUAGE_OPTIONS}
    return language_by_code.get(value, str(value))

def _format_target_language(value):
    label_by_target = {target: label for label, target in TARGET_LANGUAGE_OPTIONS}
    return label_by_target.get(value, str(value))

def _source_language_select_state(current_value):
    labels = [label for label, _, _ in ASR_LANGUAGE_OPTIONS] + [MANUAL_LANGUAGE_LABEL]
    values = [code for _, code, _ in ASR_LANGUAGE_OPTIONS] + [MANUAL_LANGUAGE_VALUE]
    current_value = _normalize_asr_language(current_value)
    if current_value in values:
        return labels, values, values.index(current_value), current_value
    return labels, values, values.index(MANUAL_LANGUAGE_VALUE), current_value

def _target_language_select_state(current_value):
    labels = [label for label, target in TARGET_LANGUAGE_OPTIONS] + [MANUAL_LANGUAGE_LABEL]
    values = [target for _, target in TARGET_LANGUAGE_OPTIONS] + [MANUAL_LANGUAGE_VALUE]
    current_value = str(current_value or "")
    if current_value in values:
        return labels, values, values.index(current_value), current_value
    return labels, values, values.index(MANUAL_LANGUAGE_VALUE), current_value


def _subtitle_layout_settings_visibility(layout):
    return layout == "portrait_9_16", layout == "landscape"

def _seed_config_history_once():
    if st.session_state.get("config_history_seeded"):
        return
    keys = [
        "api.key", "api.base_url", "api.model", "api.llm_support_json",
        "translator_api.key", "translator_api.base_url", "translator_api.model", "translator_api.llm_support_json",
        "translator_refine_with_workflow", "enable_subtitle_proofread",
        "whisper.language", "whisper.runtime", "whisper.model",
        "target_language", "demucs", "burn_subtitles", "subtitle_layout", "subtitle_layout_profile", "subtitle_hardsub_strategy", "hardsub_translation_offset", "bilingual_translation_offset", "watermark_enabled", "watermark_text", "watermark_font_size", "watermark_offset", "portrait_source_font_size", "portrait_translation_font_size", "portrait_hardsub_translation_font_size", "portrait_bilingual_offset", "portrait_hardsub_translation_offset", "portrait_hardsub_placement", "portrait_watermark_font_size", "portrait_watermark_offset", "landscape_source_font_size", "landscape_translation_font_size", "landscape_bilingual_translation_offset", "landscape_hardsub_translation_offset", "landscape_watermark_font_size", "landscape_watermark_offset", "translation_max_workers",
        "tts_method", "sf_fish_tts.api_key", "sf_fish_tts.mode", "sf_fish_tts.voice",
        "openai_tts.api_key", "openai_tts.voice",
        "fish_tts.api_key", "fish_tts.character",
        "azure_tts.api_key", "azure_tts.voice",
        "gpt_sovits.character", "gpt_sovits.refer_mode",
        "edge_tts.voice", "sf_cosyvoice2.api_key", "f5tts.302_api",
        "max_workers",
    ]
    for key in keys:
        try:
            record_key_history(key, load_key(key))
        except Exception:
            pass
    st.session_state["config_history_seeded"] = True

def _render_diagnostics_tools():
    with st.expander(t("Diagnostics and Maintenance"), expanded=False):
        st.caption(t("Use these tools only when a task is not running."))
        c1, c2 = st.columns(2)
        if c1.button(t("Test Workflow Model"), key="diagnostics_test_workflow"):
            _run_api_check("workflow")
        if c2.button(t("Test Translation Model"), key="diagnostics_test_translator"):
            _run_api_check("translator")

        cache_dir = "output/gpt_cache"
        if st.button(t("Clear GPT Cache"), key="diagnostics_clear_gpt_cache"):
            if os.path.isdir(cache_dir):
                shutil.rmtree(cache_dir)
            st.toast(t("GPT cache cleared"), icon="✅")
            st.rerun()

def page_setting():
    _seed_config_history_once()
    _seed_api_profiles_once()

    display_language = st.selectbox("Display Language 🌐",
                                  options=list(DISPLAY_LANGUAGES.keys()),
                                  index=list(DISPLAY_LANGUAGES.values()).index(load_key("display_language")))
    if DISPLAY_LANGUAGES[display_language] != load_key("display_language"):
        update_key("display_language", DISPLAY_LANGUAGES[display_language])
        st.rerun()

    with st.expander(t("Youtube Settings"), expanded=False):
        config_input(t("Cookies from Browser"), "youtube.cookies_from_browser",
                     help=t("chrome, safari, firefox — yt-dlp reads cookies directly from your browser"))
        config_input(t("Cookies File Path"), "youtube.cookies_path",
                     help=t("Path to a Netscape-format cookies.txt file (optional, browser cookies are preferred)"))

    with st.expander(t("LLM Configuration"), expanded=False):
        st.markdown(f"**{t('Workflow Model')}**")
        _render_api_profile_manager("workflow")
        config_input(
            t("API_KEY"),
            "api.key",
            history_format_func=_mask_secret,
            on_history_select=lambda value: _apply_api_profile_from_key("workflow", value),
        )
        config_input(t("BASE_URL"), "api.base_url", help=t("Used for summary, terminology, splitting, alignment, trimming and JSON tasks"))

        c1, c2 = st.columns([4, 1])
        with c1:
            config_input(t("MODEL"), "api.model", help=t("click to check API validity")+ " 👉")
        with c2:
            if st.button("📡", key="workflow_api"):
                _run_api_check("workflow")
        _run_pending_auto_api_check("workflow")
        if st.button(t("Refresh Available Models"), key="workflow_model_list"):
            try:
                st.session_state["workflow_models"] = list_available_models("workflow")
                st.toast(t("Model list refreshed"), icon="✅")
            except Exception as e:
                st.toast(f"{t('Failed to fetch model list')}: {e}", icon="❌")
        workflow_models = st.session_state.get("workflow_models", [])
        if workflow_models:
            current_model = load_key("api.model")
            model_options = workflow_models if current_model in workflow_models else [current_model] + workflow_models
            selected_model = st.selectbox(
                t("Available Models"),
                options=model_options,
                index=model_options.index(current_model),
                key="workflow_model_select"
            )
            if selected_model != current_model:
                update_key("api.model", selected_model)
                st.rerun()
        llm_support_json = st.toggle(t("LLM JSON Format Support"), value=load_key("api.llm_support_json"), help=t("Enable if your LLM supports JSON mode output"))
        if llm_support_json != load_key("api.llm_support_json"):
            update_key("api.llm_support_json", llm_support_json)
            st.rerun()

        st.divider()
        st.markdown(f"**{t('Translation Model')}**")
        _render_api_profile_manager("translator")
        config_input(
            t("API_KEY"),
            "translator_api.key",
            history_format_func=_mask_secret,
            on_history_select=lambda value: _apply_api_profile_from_key("translator", value),
        )
        config_input(t("BASE_URL"), "translator_api.base_url", help=t("Used only for plain subtitle translation"))
        c1, c2 = st.columns([4, 1])
        with c1:
            config_input(t("MODEL"), "translator_api.model", help=t("click to check API validity")+ " 👉")
        with c2:
            if st.button("📡", key="translator_api"):
                _run_api_check("translator")
        _run_pending_auto_api_check("translator")
        # Auto-detect: show notice for remote translators (will use workflow pipeline)
        try:
            from core.utils.config_utils import is_remote_translator
            if is_remote_translator():
                st.info(t("remote_translator_notice"))
        except Exception:
            pass
        translator_support_json = st.toggle(t("LLM JSON Format Support"), value=load_key("translator_api.llm_support_json"), help=t("Keep off for plain translation models like Hy-MT2"))
        if translator_support_json != load_key("translator_api.llm_support_json"):
            update_key("translator_api.llm_support_json", translator_support_json)
            st.rerun()
        translator_refine = st.toggle(
            t("Refine Local Translator Output"),
            value=load_key("translator_refine_with_workflow"),
            help=t("Use the workflow model to reflect and polish local translator output")
        )
        if translator_refine != load_key("translator_refine_with_workflow"):
            update_key("translator_refine_with_workflow", translator_refine)
            st.rerun()
        trans_workers = st.number_input(
            t("Translation Workers"),
            min_value=1, max_value=8, value=int(load_key("translation_max_workers")),
            step=1, key="config_translation_workers_input",
            help=t("Concurrent translation threads (auto-capped at 1 for local models)")
        )
        if trans_workers != int(load_key("translation_max_workers")):
            update_key("translation_max_workers", trans_workers)
            st.rerun()
        c1, c2 = st.columns(2)
        with c1:
            trans_temp = st.number_input(
                t("Temperature"),
                min_value=0.0, max_value=2.0, value=float(load_key("translator_api.temperature")),
                step=0.1, key="config_translator_temp_input",
                help=t("0 = deterministic, higher = more creative")
            )
            if trans_temp != float(load_key("translator_api.temperature")):
                update_key("translator_api.temperature", trans_temp)
                st.rerun()
        with c2:
            trans_tokens = st.number_input(
                t("Max Tokens"),
                min_value=64, max_value=2048, value=int(load_key("translator_api.max_tokens")),
                step=64, key="config_translator_max_tokens_input",
                help=t("Max output tokens per translation request")
            )
            if trans_tokens != int(load_key("translator_api.max_tokens")):
                update_key("translator_api.max_tokens", trans_tokens)
                st.rerun()
    with st.expander(t("Subtitles Settings"), expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            stored_lang = load_key("whisper.language")
            lang_options, lang_values, current_lang_index, custom_lang = _source_language_select_state(stored_lang)
            selected_lang = st.selectbox(
                t("Recog Lang"),
                options=lang_options,
                index=current_lang_index,
                key="subtitle_recog_lang",
            )
            selected_code = lang_values[lang_options.index(selected_lang)]
            if selected_code == MANUAL_LANGUAGE_VALUE:
                manual_code = st.text_input(
                    t("Recognition Language Code"),
                    value=custom_lang if custom_lang != MANUAL_LANGUAGE_VALUE else "",
                    help=t("Use a Whisper language code, such as ja, ko, fr, or auto"),
                    key="subtitle_recog_lang_manual",
                ).strip()
                if manual_code and manual_code != str(stored_lang):
                    update_key("whisper.language", manual_code)
                    st.rerun()
                selected_code = manual_code or str(stored_lang)
            elif selected_code != stored_lang:
                update_key("whisper.language", selected_code)
                st.rerun()

        # Check spacy model availability for selected language
        try:
            from core.spacy_utils.load_nlp_model import check_spacy_model_installed
            spacy_model, spacy_ok = check_spacy_model_installed(selected_code)
            if not spacy_ok:
                st.warning(t("spacy_model_missing").format(model=spacy_model))
        except Exception:
            pass

        runtime_options = ["local", "mlx"]
        current_runtime = load_key("whisper.runtime")
        if current_runtime not in runtime_options:
            current_runtime = "mlx"
            update_key("whisper.runtime", current_runtime)
        runtime_labels = {
            "local": t("WhisperX / faster-whisper"),
            "mlx": t("MLX Whisper / Metal"),
        }
        runtime = st.selectbox(
            t("ASR Runtime"),
            options=runtime_options,
            index=runtime_options.index(current_runtime),
            format_func=lambda value: runtime_labels.get(value, value),
            help=t("Choose WhisperX for stricter alignment or MLX Whisper for Apple Silicon Metal acceleration"),
            key="subtitle_runtime_select",
        )
        if runtime != load_key("whisper.runtime"):
            update_key("whisper.runtime", runtime)
            st.rerun()
        if runtime in ("local", "mlx"):
            whisper_models = ["large-v3"]
            current_whisper_model = load_key("whisper.model")
            if current_whisper_model not in whisper_models:
                current_whisper_model = "large-v3"
            selected_whisper = st.selectbox(
                t("Whisper Model Size"),
                options=whisper_models,
                index=whisper_models.index(current_whisper_model),
                help=t("Whisper large-v3 model"),
                key="subtitle_whisper_model",
            )
            if selected_whisper != current_whisper_model:
                update_key("whisper.model", selected_whisper)
                st.rerun()

        with c2:
            current_target = load_key("target_language")
            target_options, target_values, current_target_index, custom_target = _target_language_select_state(current_target)
            selected_target = st.selectbox(
                t("Target Lang"),
                options=target_options,
                index=current_target_index,
                help=t("Input any language in natural language, as long as llm can understand"),
                key="subtitle_target_lang",
            )
            selected_target_val = target_values[target_options.index(selected_target)]
            if selected_target_val == MANUAL_LANGUAGE_VALUE:
                manual_target = st.text_input(
                    t("Target Language Name"),
                    value=custom_target if custom_target != MANUAL_LANGUAGE_VALUE else "",
                    help=t("Input any language in natural language, as long as llm can understand"),
                    key="subtitle_target_lang_manual",
                ).strip()
                if manual_target and manual_target != str(current_target):
                    update_key("target_language", manual_target)
                    st.rerun()
            elif selected_target_val != current_target:
                update_key("target_language", selected_target_val)
                st.rerun()

        _render_lang_profile_manager()

        demucs = st.toggle(t("Vocal separation enhance"), value=load_key("demucs"), help=t("Recommended for videos with loud background noise, but will increase processing time"))
        if demucs != load_key("demucs"):
            update_key("demucs", demucs)
            st.rerun()

        burn_subtitles = st.toggle(t("Burn-in Subtitles"), value=load_key("burn_subtitles"), help=t("Whether to burn subtitles into the video, will increase processing time"))
        if burn_subtitles != load_key("burn_subtitles"):
            update_key("burn_subtitles", burn_subtitles)
            st.rerun()

        layout_options = {
            t("Auto subtitle layout"): "auto",
            t("Landscape subtitle layout"): "landscape",
            t("Portrait 9:16 subtitle layout"): "portrait_9_16",
        }
        current_layout = load_key("subtitle_layout")
        if current_layout not in layout_options.values():
            current_layout = "auto"
        selected_layout_label = st.selectbox(
            t("Subtitle Burn Layout"),
            options=list(layout_options.keys()),
            index=list(layout_options.values()).index(current_layout),
            help=t("Automatically use a mid-lower floating bilingual subtitle layout for 9:16 portrait videos"),
            key="subtitle_burn_layout",
        )
        selected_layout = layout_options[selected_layout_label]
        if selected_layout != current_layout:
            update_key("subtitle_layout", selected_layout)
            st.rerun()

        show_portrait_settings, show_landscape_settings = _subtitle_layout_settings_visibility(
            selected_layout
        )

        if show_portrait_settings:
            st.caption(t("9:16 Portrait Subtitle Settings"))
            st.caption(t("Portrait font sizes use a 576px-wide reference"))
            p_font_c1, p_font_c2 = st.columns(2)
            with p_font_c1:
                portrait_source_font_size = st.number_input(
                    t("Portrait Source Font Size"),
                    min_value=24,
                    max_value=160,
                    value=int(load_key("portrait_source_font_size")),
                    step=1,
                    key="config_portrait_source_font_size_input",
                    help=t("Portrait font sizes use a 576px-wide reference"),
                )
                if portrait_source_font_size != int(load_key("portrait_source_font_size")):
                    update_key("portrait_source_font_size", portrait_source_font_size)
                    st.rerun()
            with p_font_c2:
                portrait_translation_font_size = st.number_input(
                    t("Portrait Translation Font Size"),
                    min_value=24,
                    max_value=160,
                    value=int(load_key("portrait_translation_font_size")),
                    step=1,
                    key="config_portrait_translation_font_size_input",
                    help=t("Portrait font sizes use a 576px-wide reference"),
                )
                if portrait_translation_font_size != int(load_key("portrait_translation_font_size")):
                    update_key("portrait_translation_font_size", portrait_translation_font_size)
                    st.rerun()

            portrait_bilingual_offset = st.number_input(
                t("Portrait Bilingual Offset"),
                min_value=-500,
                max_value=500,
                value=int(load_key("portrait_bilingual_offset")),
                step=5,
                key="config_portrait_bilingual_offset_input",
                help=t("Positive portrait offsets move the complete group upward"),
            )
            if portrait_bilingual_offset != int(load_key("portrait_bilingual_offset")):
                update_key("portrait_bilingual_offset", portrait_bilingual_offset)
                st.rerun()

            p_hard_c1, p_hard_c2 = st.columns(2)
            with p_hard_c1:
                portrait_hardsub_font_size = st.number_input(
                    t("Portrait Hard Subtitle Translation Font Size"),
                    min_value=24,
                    max_value=160,
                    value=int(load_key("portrait_hardsub_translation_font_size")),
                    step=1,
                    key="config_portrait_hardsub_translation_font_size_input",
                    help=t("The encoded source hard-subtitle font cannot be changed"),
                )
                if portrait_hardsub_font_size != int(load_key("portrait_hardsub_translation_font_size")):
                    update_key("portrait_hardsub_translation_font_size", portrait_hardsub_font_size)
                    st.rerun()
            with p_hard_c2:
                portrait_hardsub_offset = st.number_input(
                    t("Portrait Hard Subtitle Translation Offset"),
                    min_value=-500,
                    max_value=500,
                    value=int(load_key("portrait_hardsub_translation_offset")),
                    step=5,
                    key="config_portrait_hardsub_translation_offset_input",
                    help=t("Positive portrait offsets move the complete group upward"),
                )
                if portrait_hardsub_offset != int(load_key("portrait_hardsub_translation_offset")):
                    update_key("portrait_hardsub_translation_offset", portrait_hardsub_offset)
                    st.rerun()

            try:
                current_placement = load_key("portrait_hardsub_placement")
            except KeyError:
                current_placement = "auto"
                update_key("portrait_hardsub_placement", current_placement)
            placement_options = ["auto", "above", "below"]
            placement_labels = {
                "auto": t("Auto (smart)"),
                "above": t("Always Above Hard Subtitle"),
                "below": t("Always Below Hard Subtitle"),
            }
            if current_placement not in placement_options:
                current_placement = "auto"
            selected_placement = st.selectbox(
                t("Portrait Hard Subtitle Translation Placement"),
                placement_options,
                index=placement_options.index(current_placement),
                format_func=lambda value: placement_labels.get(value, value),
                key="portrait_hardsub_placement_select",
                help=t("\"auto\": smart placement based on hard-sub position — places translation above when hard-sub is near the bottom"),
            )
            if selected_placement != current_placement:
                update_key("portrait_hardsub_placement", selected_placement)
                st.rerun()

            p_wm_c1, p_wm_c2 = st.columns(2)
            with p_wm_c1:
                portrait_watermark_font_size = st.number_input(
                    t("Portrait Watermark Font Size"),
                    min_value=12,
                    max_value=96,
                    value=int(load_key("portrait_watermark_font_size")),
                    step=1,
                    key="config_portrait_watermark_font_size_input",
                    help=t("Portrait font sizes use a 576px-wide reference"),
                )
                if portrait_watermark_font_size != int(load_key("portrait_watermark_font_size")):
                    update_key("portrait_watermark_font_size", portrait_watermark_font_size)
                    st.rerun()
            with p_wm_c2:
                portrait_watermark_offset = st.number_input(
                    t("Portrait Watermark Offset"),
                    min_value=-500,
                    max_value=500,
                    value=int(load_key("portrait_watermark_offset")),
                    step=5,
                    key="config_portrait_watermark_offset_input",
                    help=t("Positive portrait offsets move the complete group upward"),
                )
                if portrait_watermark_offset != int(load_key("portrait_watermark_offset")):
                    update_key("portrait_watermark_offset", portrait_watermark_offset)
                    st.rerun()

        current_layout_profile = load_key("subtitle_layout_profile")
        if current_layout_profile != "default":
            update_key("subtitle_layout_profile", "default")
            current_layout_profile = "default"

        hardsub_options = {
            t("Auto hard subtitle handling"): "auto",
            t("No original hard subtitles"): "none",
            t("Original video has source hard subtitles"): "source_hardsub",
        }
        current_hardsub = load_key("subtitle_hardsub_strategy")
        if current_hardsub not in hardsub_options.values():
            current_hardsub = "auto"
        selected_hardsub_label = st.selectbox(
            t("Original Hard Subtitle Handling"),
            options=list(hardsub_options.keys()),
            index=list(hardsub_options.values()).index(current_hardsub),
            help=t("When source hard subtitles already exist, burn only translated subtitles above them to avoid overlap"),
            key="subtitle_hardsub_strategy",
        )
        selected_hardsub = hardsub_options[selected_hardsub_label]
        if selected_hardsub != current_hardsub:
            update_key("subtitle_hardsub_strategy", selected_hardsub)
            st.rerun()

        if show_landscape_settings:
            st.divider()
            st.caption(t("Landscape Subtitle Settings"))
            l_font_c1, l_font_c2 = st.columns(2)
            with l_font_c1:
                landscape_source_font_size = st.number_input(
                    t("Landscape Source Font Size"),
                    min_value=20, max_value=100,
                    value=int(load_key("landscape_source_font_size")), step=1,
                    key="config_landscape_source_font_size_input",
                    help=t("Reference font size at 1080p; scales with video height")
                )
                if landscape_source_font_size != int(load_key("landscape_source_font_size")):
                    update_key("landscape_source_font_size", landscape_source_font_size)
                    st.rerun()
            with l_font_c2:
                landscape_translation_font_size = st.number_input(
                    t("Landscape Translation Font Size"),
                    min_value=20, max_value=100,
                    value=int(load_key("landscape_translation_font_size")), step=1,
                    key="config_landscape_translation_font_size_input",
                    help=t("Reference font size at 1080p; scales with video height")
                )
                if landscape_translation_font_size != int(load_key("landscape_translation_font_size")):
                    update_key("landscape_translation_font_size", landscape_translation_font_size)
                    st.rerun()

            try:
                landscape_hardsub_offset = int(load_key("landscape_hardsub_translation_offset"))
            except Exception:
                landscape_hardsub_offset = 0
            landscape_hardsub_offset = max(-500, min(500, landscape_hardsub_offset))
            l_hardsub_offset = st.number_input(
                t("Landscape Hard Subtitle Offset"),
                min_value=-500, max_value=500, value=landscape_hardsub_offset, step=5,
                key="config_landscape_hardsub_translation_offset_input",
                help=t("Landscape: vertical offset when source hard subtitles already exist")
            )
            if l_hardsub_offset != int(load_key("landscape_hardsub_translation_offset")):
                update_key("landscape_hardsub_translation_offset", l_hardsub_offset)
                st.rerun()

            try:
                landscape_bilingual_offset = int(load_key("landscape_bilingual_translation_offset"))
            except Exception:
                landscape_bilingual_offset = 0
            landscape_bilingual_offset = max(-500, min(500, landscape_bilingual_offset))
            l_bilingual_offset = st.number_input(
                t("Landscape Bilingual Offset"),
                min_value=-500, max_value=500, value=landscape_bilingual_offset, step=5,
                key="config_landscape_bilingual_translation_offset_input",
                help=t("Landscape: vertical offset for bilingual subtitle block; positive moves up, negative moves down")
            )
            if l_bilingual_offset != landscape_bilingual_offset:
                update_key("landscape_bilingual_translation_offset", l_bilingual_offset)
                st.rerun()

            l_wm_c1, l_wm_c2 = st.columns(2)
            with l_wm_c1:
                l_wm_font_size = st.number_input(
                    t("Landscape Watermark Font Size"),
                    min_value=10, max_value=64, value=int(load_key("landscape_watermark_font_size")),
                    step=1, key="config_landscape_watermark_font_size_input"
                )
                if l_wm_font_size != int(load_key("landscape_watermark_font_size")):
                    update_key("landscape_watermark_font_size", l_wm_font_size)
                    st.rerun()
            with l_wm_c2:
                try:
                    l_wm_offset = int(load_key("landscape_watermark_offset"))
                except Exception:
                    l_wm_offset = _7_sub_into_vid.LANDSCAPE_WATERMARK_DEFAULT_OFFSET
                l_wm_offset = max(-500, min(500, l_wm_offset))
                l_wm_offset_val = st.number_input(
                    t("Landscape Watermark Offset"),
                    min_value=-500, max_value=500, value=l_wm_offset, step=5,
                    key="config_landscape_watermark_offset_input",
                    help=t("Landscape: pixels between watermark and top subtitle line")
                )
                if l_wm_offset_val != int(load_key("landscape_watermark_offset")):
                    update_key("landscape_watermark_offset", l_wm_offset_val)
                    st.rerun()

            effective_watermark_gap = _7_sub_into_vid.landscape_watermark_effective_gap(l_wm_offset_val)
            st.caption(
                f'{t("Landscape watermark default gap")}: '
                f'{_7_sub_into_vid.LANDSCAPE_WATERMARK_SUBTITLE_GAP}px · '
                f'{t("Current effective watermark gap")}: {effective_watermark_gap}px · '
                f'{t("Default offset")}: {_7_sub_into_vid.LANDSCAPE_WATERMARK_DEFAULT_OFFSET}px'
            )
            if effective_watermark_gap <= 0:
                st.warning(t("Watermark may overlap bilingual subtitles"))

        st.divider()
        watermark_text = st.text_input(
            t("Watermark Text"),
            value=str(load_key("watermark_text") or _7_sub_into_vid.WATERMARK_TEXT),
            key="config_watermark_text_input",
            help=t("Customize the watermark name shown above bilingual subtitles"),
        )
        if watermark_text != str(load_key("watermark_text")):
            update_key("watermark_text", watermark_text or _7_sub_into_vid.WATERMARK_TEXT)
            st.rerun()

        watermark_enabled = st.toggle(t("Watermark") + f"：{watermark_text}", value=load_key("watermark_enabled"), help=t("Show semi-transparent watermark above subtitles in bilingual mode"))
        if watermark_enabled != load_key("watermark_enabled"):
            update_key("watermark_enabled", watermark_enabled)
            st.rerun()

        st.divider()
        enable_proofread = st.toggle(
            t("Automatically proofread final subtitles"),
            value=load_key("enable_subtitle_proofread"),
            help=t("Check final SRT structure, timing, alignment and suspicious fragments before video merge")
        )
        if enable_proofread != load_key("enable_subtitle_proofread"):
            update_key("enable_subtitle_proofread", enable_proofread)
            st.rerun()

        st.caption(t("Ambiguity Review Report"))
        enable_ambiguity = st.toggle(
            t("Enable Ambiguity Check"),
            value=load_key("enable_ambiguity_check"),
            help=t("Use the workflow model to detect ambiguous words/phrases in local translator output")
        )
        if enable_ambiguity != load_key("enable_ambiguity_check"):
            update_key("enable_ambiguity_check", enable_ambiguity)
            st.rerun()
        if st.button(t("Generate Ambiguity Report"), key="gen_ambiguity_sidebar",
                     help=t("Run ambiguity check on already-translated subtitles using the workflow model"),
                     disabled=not enable_ambiguity):
            st.session_state["trigger_ambiguity_check"] = True
            st.rerun()

        upload_copy = st.toggle(t("Generate upload copy suggestions"), value=load_key("enable_upload_copy_suggestions"))
        if upload_copy != load_key("enable_upload_copy_suggestions"):
            update_key("enable_upload_copy_suggestions", upload_copy)
            st.rerun()
    _render_diagnostics_tools()
    with st.expander(t("Dubbing Settings"), expanded=False):
        tts_methods = ["azure_tts", "openai_tts", "fish_tts", "sf_fish_tts", "edge_tts", "gpt_sovits", "custom_tts", "sf_cosyvoice2", "f5tts"]
        current_tts = load_key("tts_method")
        if current_tts not in tts_methods:
            current_tts = tts_methods[0]
        select_tts = st.selectbox(
            t("TTS Method"),
            options=tts_methods,
            index=tts_methods.index(current_tts),
            key="dubbing_tts_select",
        )
        if select_tts != current_tts:
            update_key("tts_method", select_tts)
            st.rerun()

        if select_tts == "sf_fish_tts":
            val = st.text_input(t("SiliconFlow API Key"), value=str(load_key("sf_fish_tts.api_key")), key="dub_sf_key")
            if val != str(load_key("sf_fish_tts.api_key")):
                update_key("sf_fish_tts.api_key", val); st.rerun()
            mode_options = {"preset": t("Preset"), "custom": t("Refer_stable"), "dynamic": t("Refer_dynamic")}
            current_mode = load_key("sf_fish_tts.mode")
            if current_mode not in mode_options: current_mode = "preset"
            selected_mode = st.selectbox(t("Mode Selection"), options=list(mode_options.keys()),
                format_func=lambda v: mode_options.get(v, v),
                index=list(mode_options.keys()).index(current_mode), key="dub_sf_mode")
            if selected_mode != current_mode:
                update_key("sf_fish_tts.mode", selected_mode); st.rerun()
            if selected_mode == "preset":
                val = st.text_input("Voice", value=str(load_key("sf_fish_tts.voice")), key="dub_sf_voice")
                if val != str(load_key("sf_fish_tts.voice")): update_key("sf_fish_tts.voice", val); st.rerun()

        elif select_tts == "openai_tts":
            val = st.text_input("302ai API", value=str(load_key("openai_tts.api_key")), key="dub_oai_key")
            if val != str(load_key("openai_tts.api_key")): update_key("openai_tts.api_key", val); st.rerun()
            val = st.text_input(t("OpenAI Voice"), value=str(load_key("openai_tts.voice")), key="dub_oai_voice")
            if val != str(load_key("openai_tts.voice")): update_key("openai_tts.voice", val); st.rerun()

        elif select_tts == "fish_tts":
            val = st.text_input("302ai API", value=str(load_key("fish_tts.api_key")), key="dub_fish_key")
            if val != str(load_key("fish_tts.api_key")): update_key("fish_tts.api_key", val); st.rerun()
            fish_tts_characters = list(load_key("fish_tts.character_id_dict").keys())
            current_char = load_key("fish_tts.character")
            if current_char not in fish_tts_characters: current_char = fish_tts_characters[0] if fish_tts_characters else ""
            if fish_tts_characters:
                selected_char = st.selectbox(t("Fish TTS Character"), options=fish_tts_characters,
                    index=fish_tts_characters.index(current_char), key="dub_fish_char")
                if selected_char != current_char: update_key("fish_tts.character", selected_char); st.rerun()

        elif select_tts == "azure_tts":
            val = st.text_input("302ai API", value=str(load_key("azure_tts.api_key")), key="dub_az_key")
            if val != str(load_key("azure_tts.api_key")): update_key("azure_tts.api_key", val); st.rerun()
            val = st.text_input(t("Azure Voice"), value=str(load_key("azure_tts.voice")), key="dub_az_voice")
            if val != str(load_key("azure_tts.voice")): update_key("azure_tts.voice", val); st.rerun()

        elif select_tts == "gpt_sovits":
            st.info(t("Please refer to Github homepage for GPT_SoVITS configuration"))
            val = st.text_input(t("SoVITS Character"), value=str(load_key("gpt_sovits.character")), key="dub_gs_char")
            if val != str(load_key("gpt_sovits.character")): update_key("gpt_sovits.character", val); st.rerun()
            refer_mode_options = {1: t("Mode 1"), 2: t("Mode 2"), 3: t("Mode 3")}
            current_ref = load_key("gpt_sovits.refer_mode")
            if current_ref not in refer_mode_options: current_ref = 1
            selected_refer_mode = st.selectbox(t("Refer Mode"), options=list(refer_mode_options.keys()),
                format_func=lambda v: refer_mode_options.get(v, str(v)),
                index=list(refer_mode_options.keys()).index(current_ref),
                help=t("Configure reference audio mode for GPT-SoVITS"), key="dub_gs_ref")
            if selected_refer_mode != current_ref: update_key("gpt_sovits.refer_mode", selected_refer_mode); st.rerun()

        elif select_tts == "edge_tts":
            val = st.text_input(t("Edge TTS Voice"), value=str(load_key("edge_tts.voice")), key="dub_edge_voice")
            if val != str(load_key("edge_tts.voice")): update_key("edge_tts.voice", val); st.rerun()

        elif select_tts == "sf_cosyvoice2":
            val = st.text_input(t("SiliconFlow API Key"), value=str(load_key("sf_cosyvoice2.api_key")), key="dub_cos_key")
            if val != str(load_key("sf_cosyvoice2.api_key")): update_key("sf_cosyvoice2.api_key", val); st.rerun()

        elif select_tts == "f5tts":
            val = st.text_input("302ai API", value=str(load_key("f5tts.302_api")), key="dub_f5_key")
            if val != str(load_key("f5tts.302_api")): update_key("f5tts.302_api", val); st.rerun()
def check_api(api_role="workflow"):
    try:
        if api_role == "translator":
            resp = ask_gpt("Translate to Simplified Chinese, return only the translation: Hello",
                          resp_type=None, log_title='None', api_role=api_role)
            return bool(str(resp).strip())

        resp = ask_gpt("This is a test, response 'message':'success' in json format.",
                      resp_type="json", log_title='None', api_role=api_role)
        if isinstance(resp, dict):
            return resp.get('message') == 'success'
        return bool(str(resp).strip())
    except Exception:
        return False

if __name__ == "__main__":
    check_api()
