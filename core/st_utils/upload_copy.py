import hashlib
import json
import os
import re

import streamlit as st

from core import _1_ytdlp, _7_sub_into_vid
from core.job_manifest import manifest_input_video
from core.utils import ask_gpt, load_key
from translations.translations import translate as t


UPLOAD_COPY_SUGGESTIONS = "output/log/upload_copy_suggestions.json"
UPLOAD_COPY_SCHEMA_VERSION = "zh_only_v2"
VIDEO_DESCRIPTION_PATH = "output/video_description.md"
SKIP_UPLOAD_COPY_AUTOGENERATE_ONCE = "skip_upload_copy_autogenerate_once"


def suppress_upload_copy_autogenerate_once():
    st.session_state[SKIP_UPLOAD_COPY_AUTOGENERATE_ONCE] = True


def consume_upload_copy_autogenerate_setting():
    return not bool(st.session_state.pop(SKIP_UPLOAD_COPY_AUTOGENERATE_ONCE, False))


def _read_text_file(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _clean_description_for_upload(description):
    blocked_patterns = [
        r"https?://\S+",
        r"\bsubscribe\b",
        r"\bfollow\b",
        r"\blike and subscribe\b",
        r"\bnewsletter\b",
        r"\bdownload the app\b",
        r"\bwatch more\b",
        r"\bclick here\b",
        r"\bvisit\b.*\bwebsite\b",
        r"\bCBS News 24/7\b",
        r"\bpremier anchored streaming news service\b",
        r"^\s*#",
        r"@\w+",
    ]
    cleaned_lines = []
    for line in str(description or "").splitlines():
        text = line.strip()
        if not text:
            cleaned_lines.append("")
            continue
        if any(re.search(pattern, text, re.I) for pattern in blocked_patterns):
            continue
        cleaned_lines.append(text)
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _current_original_video_path():
    manifest_video = manifest_input_video()
    if manifest_video:
        return manifest_video
    try:
        return _1_ytdlp.find_video_files()
    except Exception:
        allowed_exts = tuple(f".{ext.lower()}" for ext in load_key("allowed_video_formats"))
        candidates = []
        if os.path.isdir("output"):
            for name in os.listdir("output"):
                path = os.path.join("output", name)
                stem, ext = os.path.splitext(name)
                if not os.path.isfile(path) or ext.lower() not in allowed_exts:
                    continue
                if stem.startswith("manual_") or re.search(r"(?:^|_)sub(?:_v\d+)?$", stem):
                    continue
                candidates.append(path)
        return max(candidates, key=os.path.getmtime) if candidates else ""


def _current_video_title():
    video_path = _current_original_video_path()
    if not video_path:
        return ""
    title = os.path.splitext(os.path.basename(video_path))[0]
    title = re.sub(r"[_]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _compact_text_for_prompt(text, limit=12000):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    head = text[: limit // 2].strip()
    tail = text[-limit // 2 :].strip()
    return f"{head}\n...[middle omitted]...\n{tail}"


def _parse_srt_file(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        content = f.read().strip()
    if not content:
        return []
    entries = []
    for block in re.split(r"\n\s*\n", content):
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        entries.append({
            "index": lines[0],
            "timestamp": lines[1],
            "text": "\n".join(lines[2:]).strip(),
            "text_lines": lines[2:],
        })
    return entries


def _split_bilingual_entries(entries, first_line="trans"):
    src_entries = []
    trans_entries = []
    for entry in entries:
        text_lines = entry.get("text_lines") or str(entry.get("text", "")).splitlines()
        if not text_lines:
            continue
        first_text = text_lines[0].strip()
        second_text = "\n".join(text_lines[1:]).strip()
        if first_line == "src":
            src_text = first_text
            trans_text = second_text
        else:
            trans_text = first_text
            src_text = second_text
        src_entries.append({**entry, "text": src_text or trans_text})
        trans_entries.append({**entry, "text": trans_text or src_text})
    return src_entries, trans_entries


def _find_latest_bilingual_subtitle_path():
    candidates = []
    try:
        video_path = _current_original_video_path()
        if video_path:
            subtitle_paths = _7_sub_into_vid.get_default_subtitle_paths(video_path)
            for key in ("trans_src", "src_trans"):
                path = subtitle_paths.get(key)
                if path and os.path.exists(path):
                    candidates.append(path)
    except Exception:
        pass

    if os.path.isdir("output"):
        for name in os.listdir("output"):
            if name.endswith(("_trans_src.srt", "_src_trans.srt")):
                path = os.path.join("output", name)
                if os.path.isfile(path):
                    candidates.append(path)

    if not candidates:
        return ""
    return max(set(candidates), key=os.path.getmtime)


def _latest_bilingual_subtitle_content():
    subtitle_path = _find_latest_bilingual_subtitle_path()
    if not subtitle_path:
        return {}
    try:
        entries = _parse_srt_file(subtitle_path)
        first_line = "trans" if os.path.basename(subtitle_path).endswith("_trans_src.srt") else "src"
        src_entries, trans_entries = _split_bilingual_entries(entries, first_line=first_line)
    except Exception:
        raw = _read_text_file(subtitle_path)
        return {
            "path": subtitle_path,
            "source_text": raw,
            "translation_text": "",
            "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        }

    source_text = " ".join(item.get("text", "") for item in src_entries).strip()
    translation_text = " ".join(item.get("text", "") for item in trans_entries).strip()
    source_blob = f"{subtitle_path}\n{source_text}\n{translation_text}"
    return {
        "path": subtitle_path,
        "source_text": source_text,
        "translation_text": translation_text,
        "sha256": hashlib.sha256(source_blob.encode("utf-8")).hexdigest(),
    }


def _valid_upload_copy_result(response_data):
    if not isinstance(response_data, dict):
        return {"status": "error", "message": "Response is not a JSON object"}
    required = ["original", "suggestions"]
    missing = [key for key in required if key not in response_data]
    if missing:
        return {"status": "error", "message": f"Missing required key(s): {', '.join(missing)}"}
    suggestions = response_data.get("suggestions")
    if not isinstance(suggestions, list) or len(suggestions) != 10:
        return {"status": "error", "message": "suggestions must contain exactly 10 items"}
    for index, item in enumerate(suggestions, start=1):
        if not isinstance(item, dict):
            return {"status": "error", "message": f"suggestion {index} is not an object"}
        missing = [key for key in ("zh_title", "zh_description") if key not in item]
        if missing:
            return {"status": "error", "message": f"suggestion {index} missing: {', '.join(missing)}"}
    return {"status": "success", "message": "Upload copy generated"}


def _upload_copy_source(title=None, description=None):
    if title is None:
        title = _current_video_title()
    if description is None:
        description = _clean_description_for_upload(_read_text_file(VIDEO_DESCRIPTION_PATH))
    subtitle_data = _latest_bilingual_subtitle_content()
    source_text = f"{title}\n\n{description}\n\n{subtitle_data.get('sha256', '')}"
    return {
        "schema": UPLOAD_COPY_SCHEMA_VERSION,
        "title": title,
        "subtitle_path": subtitle_data.get("path", ""),
        "subtitle_sha256": subtitle_data.get("sha256", ""),
        "description_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
    }


def _load_stored_upload_copy():
    if not os.path.exists(UPLOAD_COPY_SUGGESTIONS):
        return None
    try:
        with open(UPLOAD_COPY_SUGGESTIONS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _load_cached_upload_copy(source):
    data = _load_stored_upload_copy()
    if not data:
        return None
    if data.get("source") != source:
        return None
    return data


def generate_upload_copy_suggestions(force=False):
    title = _current_video_title()
    description = _clean_description_for_upload(_read_text_file(VIDEO_DESCRIPTION_PATH))
    subtitle_data = _latest_bilingual_subtitle_content()
    source = _upload_copy_source(title, description)
    if not force:
        cached = _load_cached_upload_copy(source)
        if cached:
            return cached

    if not title and not description and not subtitle_data:
        return None

    prompt = f"""
You are a Chinese video publishing editor.

Task:
1. Use the latest reviewed bilingual subtitles as the primary source of truth for the video content.
2. Use the original video title and cleaned original description only as background context.
3. Provide an upload-ready original title and original description in Simplified Chinese based on the actual subtitle content.
4. Create exactly 10 catchy upload candidates in Simplified Chinese based on the final subtitle content.

Hard limits:
- Chinese title: about 15 Chinese characters.
- Chinese description: about 100 Chinese characters.
- Keep names, brands, titles, and acronyms accurate.
- Do not use clickbait that misrepresents the video.
- Do not include social media promotion, channel promotion, ads, links, subscribe/follow calls, or unrelated boilerplate.
- Do not output English title or English description fields.
- Output JSON only.

Original title:
{title}

Cleaned original description for background only:
{description}

Latest bilingual subtitle file:
{subtitle_data.get("path", "")}

Latest source subtitles:
{_compact_text_for_prompt(subtitle_data.get("source_text", ""), 12000)}

Latest translated subtitles:
{_compact_text_for_prompt(subtitle_data.get("translation_text", ""), 10000)}

JSON schema:
{{
  "original": {{
    "zh_title": "Chinese title around 15 Chinese characters",
    "zh_description": "Chinese description around 100 Chinese characters"
  }},
  "suggestions": [
    {{
      "zh_title": "Chinese title around 15 Chinese characters",
      "zh_description": "Chinese description around 100 Chinese characters"
    }}
  ]
}}
""".strip()
    result = ask_gpt(
        prompt,
        resp_type="json",
        valid_def=_valid_upload_copy_result,
        log_title="upload_copy_suggestions",
        api_role="workflow",
    )
    result["source"] = source
    os.makedirs(os.path.dirname(UPLOAD_COPY_SUGGESTIONS), exist_ok=True)
    with open(UPLOAD_COPY_SUGGESTIONS, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def render_upload_copy_suggestions(
    is_task_running=None,
    auto_generate_missing=True,
):
    if not (_current_video_title() or os.path.exists(VIDEO_DESCRIPTION_PATH) or _find_latest_bilingual_subtitle_path()):
        return
    is_task_running = is_task_running or (lambda: False)
    st.subheader(t("Upload Copy Suggestions"))
    title = _current_video_title()
    description = _clean_description_for_upload(_read_text_file(VIDEO_DESCRIPTION_PATH))
    source = _upload_copy_source(title, description)
    data = _load_cached_upload_copy(source)
    if data is None and not auto_generate_missing:
        data = _load_stored_upload_copy()

    c1, c2 = st.columns([1, 1])
    with c1:
        generate = st.button(
            t("Generate Upload Copy Suggestions"),
            key="generate_upload_copy_suggestions",
            disabled=is_task_running(),
        )
    with c2:
        regenerate = st.button(
            t("Regenerate Upload Copy Suggestions"),
            key="regenerate_upload_copy_suggestions",
            disabled=is_task_running(),
        )
    if generate or regenerate or (data is None and auto_generate_missing):
        with st.spinner(t("Generating upload copy suggestions...")):
            data = generate_upload_copy_suggestions(force=regenerate)

    if not data:
        st.caption(t("No video title or description found"))
        return

    original = data.get("original", {})
    st.markdown(f"**{t('Original Title')}**")
    st.write(original.get("zh_title", ""))
    st.markdown(f"**{t('Original Description')}**")
    st.write(original.get("zh_description", ""))

    rows = []
    for index, item in enumerate(data.get("suggestions", []), start=1):
        rows.append({
            t("Index"): index,
            t("Chinese Title"): item.get("zh_title", ""),
            t("Chinese Description"): item.get("zh_description", ""),
        })
    if rows:
        st.markdown(f"**{t('Suggested Viral Titles and Descriptions')}**")
        st.dataframe(rows, width="stretch", hide_index=True)
