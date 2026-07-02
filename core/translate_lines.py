from core.prompts import generate_shared_prompt, get_prompt_faithfulness, get_prompt_expressiveness, get_prompt_refine_translator_result
import re
import sys
import os
import json
import threading
import urllib.error
import urllib.request
from urllib.parse import urlparse
from difflib import SequenceMatcher
from rich.panel import Panel
from rich.console import Console
from rich.table import Table
from rich import box
from core.utils import *
from core.utils.models import _4_3_AMBIGUITY
console = Console()
VIDEO_DESCRIPTION_PATH = "output/video_description.md"
AMBIGUITY_LOCK = threading.Lock()
TRANSLATOR_HEALTH_LOCK = threading.Lock()
TRANSLATOR_HEALTH_CACHE = {}

def _read_video_description():
    if not os.path.exists(VIDEO_DESCRIPTION_PATH):
        return None
    with open(VIDEO_DESCRIPTION_PATH, "r", encoding="utf-8") as f:
        description = f.read().strip()
    return description or None

def _with_video_description(summary_prompt):
    if summary_prompt and "### Video Description" in str(summary_prompt):
        return summary_prompt
    video_description = _read_video_description()
    if not video_description:
        return summary_prompt
    return f"""{summary_prompt or ""}

### Video Description
Use this creator-provided description as translation context. It may disambiguate words with multiple meanings, names, topics, and domain-specific terms. For example, in a film/interview context, "shoot" or "shooting" usually means filming/拍摄 rather than shooting with a weapon/射击.
Important: WhisperX may misspell proper nouns, names, titles, teams, brands, or places. If a subtitle contains a word that looks or sounds similar to a proper noun in the video description, normalize the translation to the exact proper noun from the description. For example, if the description mentions "Gout Gout" but the subtitle says "Gaut", "Gao", or "Gout", treat it as "Gout Gout" when context supports that reading.
<video_description>
{video_description}
</video_description>""".strip()

POLLUTION_MARKERS = [
    # Chinese prompt text — model echoed the instruction
    "将其翻译", "仅回复翻译", "不要其他", "翻译为简体中文", "翻译成简体中文",
    "回复翻译内容", "输出翻译", "输出仅",
    # Existing markers
    "视频背景", "字幕：", "词汇表", "术语", "含义：", "文本：", "文本:",
    "Video context", "Subtitle:", "Glossary", "glossary", "Text:",
    "Return only", "Do not translate", "source term",
    "normalize similar ASR", "将类似的ASR", "统一为该确切",
]
FILLER_PATTERN = re.compile(r"\b(?:um+|uh+|er+|erm|hmm+|mm+)\b[,，、.。!！?？;；:\s]*", re.I)

def _has_translator_model():
    return bool(load_key("translator_api.model"))

def _translator_models_url(base_url):
    parsed = urlparse(str(base_url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    if path.endswith("/chat/completions"):
        path = path[: -len("/chat/completions")]
    if not path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    return parsed._replace(path=f"{path}/models", params="", query="", fragment="").geturl()

def _translator_chat_url(base_url):
    parsed = urlparse(str(base_url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    if path.endswith("/models"):
        path = path[: -len("/models")]
    if not path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    return parsed._replace(path=f"{path}/chat/completions", params="", query="", fragment="").geturl()

def _local_translator_chat_available(base_url, model, api_key):
    chat_url = _translator_chat_url(base_url)
    if not chat_url:
        return False, "invalid chat URL"
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": "Translate into Simplified Chinese only. Output only the translation.\nHello.",
                }
            ],
            "temperature": 0.1,
            "max_tokens": 32,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        chat_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read(4096).decode("utf-8", errors="ignore")
        return 200 <= response.status < 300 and bool(body.strip()), ""
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, str(exc)

def _local_translator_available(force=False, verify_chat=False):
    if not is_local_translator():
        return True
    base_url = str(load_key("translator_api.base_url") or "").strip()
    model = str(load_key("translator_api.model") or "").strip()
    api_key = str(load_key("translator_api.key") or "").strip()
    cache_key = (base_url, model, verify_chat)
    with TRANSLATOR_HEALTH_LOCK:
        if not force and cache_key in TRANSLATOR_HEALTH_CACHE:
            return TRANSLATOR_HEALTH_CACHE[cache_key]

    models_url = _translator_models_url(base_url)
    available = False
    error = ""
    if models_url:
        try:
            request = urllib.request.Request(models_url, headers={"Authorization": f"Bearer {load_key('translator_api.key')}"})
            with urllib.request.urlopen(request, timeout=3) as response:
                available = 200 <= response.status < 500
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            error = str(exc)
    if available and verify_chat:
        available, error = _local_translator_chat_available(base_url, model, api_key)

    with TRANSLATOR_HEALTH_LOCK:
        TRANSLATOR_HEALTH_CACHE[cache_key] = available
    if not available:
        console.print(
            f"[yellow]⚠️ Local translator is unavailable at {base_url}; "
            f"using workflow model for this run. {error}[/yellow]"
        )
    return available

def assert_local_translator_ready():
    if not is_local_translator() or not _has_translator_model():
        return
    if not _local_translator_available(force=True, verify_chat=True):
        raise RuntimeError(
            "Local translator is not ready. Please start Hy-MT2 and verify "
            f"{load_key('translator_api.base_url')} before running translation."
        )

def _load_bool(key, default=False):
    try:
        return bool(load_key(key))
    except KeyError:
        return default

def _contains_prompt_pollution(text):
    text = str(text)
    return any(marker in text for marker in POLLUTION_MARKERS)

def _clean_translator_output(text):
    text = str(text).strip().strip('"').strip("'").replace('\n', ' ')
    for prefix in ("译文：", "翻译：", "Translation:", "Translated subtitle:"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    # Remove common meta-text that DeepSeek sometimes prepends
    for meta_prefix in ("翻译结果：", "翻译：", "译文：", "translation:", "Translated:"):
        if text.lower().startswith(meta_prefix.lower()):
            text = text[len(meta_prefix):].strip()
    return normalize_cjk_latin_spacing(text)

def _remove_filler_words(text):
    text = FILLER_PATTERN.sub("", str(text))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _has_embedded_dialogue_question(source):
    starters = (
        "What", "Where", "When", "Why", "Who", "Whom", "Whose", "Which", "How",
        "Did", "Do", "Does", "Can", "Could", "Would", "Will", "Is", "Are", "Was",
        "Were", "Have", "Has", "Had",
    )
    answer_words = (
        "say", "tell", "know", "remember", "answer", "understand", "sure",
        "mean", "think", "guess",
    )
    return bool(
        re.search(
            rf"\b(?:{'|'.join(answer_words)})\s+(?:{'|'.join(starters)})\b.+\?",
            str(source),
        )
    )


def _target_has_question_marker(text):
    return bool(re.search(r"[？?]|(?:谁|什么|怎么|为什么|如何|是否|吗|呢|哪里|哪儿|哪个|哪些|哪种|哪位|哪边|哪一)", str(text)))


def _has_leading_affirmative_answer(source):
    return bool(
        re.match(
            r"^\s*(?:yes|yeah|yep|yup|right|correct|sure|okay|ok)\b[,.!?:;\s]*(?:i|we|he|she|they|you)?\s*(?:did|do|does|am|are|is|was|were|have|has|had|can|could|would|will)?\b",
            str(source),
            re.I,
        )
    )


def _target_has_affirmative_marker(text):
    return bool(re.search(r"(?:是的|对|对的|没错|确实|当然|嗯|好|行|可以|没事|我(?:去|做|有|是|确实)|去了|做了|确实如此)", str(text)))

SELF_INTRO_SOURCE_PATTERN = re.compile(
    r"\b[Ii]['’]?m\s+[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+){0,3}(?=\s*(?:[,.!?]|$))"
)


def _has_leading_self_intro_name(source):
    return bool(re.match(r"^\s*" + SELF_INTRO_SOURCE_PATTERN.pattern, str(source)))

def _source_self_intro_count(source):
    return len(SELF_INTRO_SOURCE_PATTERN.findall(str(source)))

def _target_self_intro_count(text):
    return len(re.findall(r"(?:我是|我叫|这里是|也是|也叫)", str(text)))

def _target_has_self_intro_marker(text):
    return bool(re.search(r"(?:我是|我叫|这里是|我是\s*[A-Za-z])", str(text)))

def _has_leading_you_know_question(source):
    return bool(re.match(r"^\s*you\s+know\s*\?\s+\S", str(source), re.I))

def _target_has_you_know_marker(text):
    return bool(re.search(r"(?:你懂|你知道|知道吧|对吧|是吧)", str(text)))

def _source_has_repetition_count(source):
    return bool(
        re.search(
            r"\b(?:like\s+)?(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+"
            r"(?:i['’]?ms|times?|tries|takes?|diet\s+cokes?)\b",
            str(source),
            re.I,
        )
    )

def _target_has_count_marker(text):
    return bool(re.search(r"(?:\d+|一|二|两|三|四|五|六|七|八|九|十|几|多).{0,4}(?:次|遍|条|个|档|回|杯|瓶|左右|大概)|(?:十|10)", str(text)))

ACKNOWLEDGEMENT_WORDS = {
    "yes", "yeah", "yep", "yup", "ok", "okay", "all", "right", "cool",
    "sure", "fine", "no", "worries", "thanks", "thank", "you",
}

def _is_short_acknowledgement_sequence(source):
    words = [word.lower() for word in re.findall(r"[A-Za-z]+", str(source))]
    return bool(words) and len(words) <= 5 and all(word in ACKNOWLEDGEMENT_WORDS for word in words)


def _translation_omission_reason(source, translation):
    source_words = re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?", str(source))
    target_text = str(translation).strip()
    target_units = len(re.findall(r"[\u3400-\u9fff]", target_text))
    target_units += len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?", target_text))
    if _source_has_repetition_count(source) and not _target_has_count_marker(target_text):
        return "source count expression appears omitted"
    if _has_embedded_dialogue_question(source) and not _target_has_question_marker(target_text):
        embedded_minimum = max(6, int(len(source_words) * 0.55 + 0.999))
        if target_units < embedded_minimum:
            return "embedded question appears omitted"
    source_clauses = [part for part in re.split(r"[.!?]+", str(source)) if part.strip()]
    if (
        len(source_clauses) >= 2
        and _has_leading_affirmative_answer(source)
        and not _target_has_affirmative_marker(target_text)
    ):
        return "leading affirmative answer appears omitted"
    if (
        len(source_clauses) >= 2
        and _has_leading_self_intro_name(source)
        and not _target_has_self_intro_marker(target_text)
    ):
        return "leading self introduction appears omitted"
    source_self_intro_count = _source_self_intro_count(source)
    if source_self_intro_count >= 2 and _target_self_intro_count(target_text) < source_self_intro_count:
        return "repeated self introduction appears omitted"
    if (
        len(source_clauses) >= 2
        and _has_leading_you_know_question(source)
        and not _target_has_you_know_marker(target_text)
    ):
        return "leading 'you know?' appears omitted"
    if len(source_clauses) >= 2 and _is_short_acknowledgement_sequence(source):
        return ""
    if len(source_clauses) >= 2:
        if len(source_words) <= 5:
            return "short multi-clause subtitle is too compressed" if target_units < len(source_clauses) * 2 else ""
        short_dialogue_minimum = max(5, int(len(source_words) * 0.60 + 0.999))
        if target_units < short_dialogue_minimum:
            return "multi-clause subtitle is too compressed"
    if len(source_words) < 8:
        return ""
    minimum_units = max(5, int(len(source_words) * 0.35 + 0.999))
    return "translation is too short for the source length" if target_units < minimum_units else ""


def translation_may_omit_content(source, translation):
    """Detect a long source sentence collapsed into an implausibly short translation."""
    return bool(_translation_omission_reason(source, translation))


def _preview_text(text, limit=100):
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text if len(text) <= limit else text[:limit - 1] + "…"

def _translation_degraded_to_punctuation(source, translation):
    source_words = re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?", str(source))
    meaningful_target = re.findall(r"[\u3400-\u9fffA-Za-z0-9]", str(translation))
    return len(source_words) >= 3 and len(meaningful_target) <= 1


def _retry_incomplete_translation(source, translation, target_language, glossary_terms):
    reason = _translation_omission_reason(source, translation)
    if not reason:
        return translation
    console.print(
        "[yellow]⚠️ Translation may omit source content; retrying complete translation "
        f"({reason}). Source: {_preview_text(source)} | Target: {_preview_text(translation)}[/yellow]"
    )
    terms = _format_line_terms(source, glossary_terms)
    terms_block = (
        f"Glossary context (do not translate this block):\n{terms}\n\n"
        if terms else ""
    )
    prompt = (
        f"Translate the complete subtitle into {target_language}. Preserve every clause and all meaning. "
        f"Do not summarize or omit content. Output only the translation.\n"
        f"{terms_block}Subtitle:\n{source}"
    )
    for _ in range(2):
        candidate = ask_gpt(prompt, resp_type=None, log_title="translate_completeness_retry", api_role="translator")
        candidate = normalize_cjk_latin_spacing(_remove_filler_words(_clean_translator_output(candidate)))
        if candidate and not _contains_prompt_pollution(candidate) and not translation_may_omit_content(source, candidate):
            return candidate
    raise ValueError(f"Translation omitted source content after retry: {source}")


def _finalize_translations_after_refine(source_lines, refined_translations, raw_translations, target_language, glossary_terms):
    final_translations = []
    for source, refined, raw in zip(source_lines, refined_translations, raw_translations):
        refined_reason = _translation_omission_reason(source, refined)
        degraded_reason = "refinement collapsed to punctuation" if _translation_degraded_to_punctuation(source, refined) else ""
        if (
            (refined_reason or degraded_reason)
            and raw
            and not _contains_prompt_pollution(raw)
            and not translation_may_omit_content(source, raw)
        ):
            console.print(
                "[yellow]⚠️ Workflow refinement may omit source content; keeping translator output "
                f"({refined_reason or degraded_reason}). Source: {_preview_text(source)} | Refined: {_preview_text(refined)} | "
                f"Translator: {_preview_text(raw)}[/yellow]"
            )
            final_translations.append(raw)
            continue
        final_translations.append(_retry_incomplete_translation(source, refined, target_language, glossary_terms))
    return final_translations

def _salvage_translator_output(text, line):
    text = _clean_translator_output(text)
    text = _remove_filler_words(text)
    if not text:
        return ""

    text_label_match = re.search(r"(?:文本|Text)\s*[:：]\s*(.+)$", text, re.I)
    if text_label_match:
        return text_label_match.group(1).strip(" .。；;")

    term_match = re.search(r"(?:术语|Terms?|Glossary)\s*[:：]\s*[^=＝:：]+[=＝:：]\s*(.+)$", text, re.I)
    if term_match:
        text = term_match.group(1).strip(" .。；;")
        text_label_match = re.search(r"(?:文本|Text)\s*[:：]\s*(.+)$", text, re.I)
        return (text_label_match.group(1) if text_label_match else text).strip(" .。；;")

    for prefix in ("术语：", "术语:", "Terms:", "Term:", "Glossary:", "文本：", "文本:", "Text:"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    if "=" in text or "＝" in text:
        right_side = re.split(r"[=＝]", text, maxsplit=1)[-1].strip(" .。；;")
        text_label_match = re.search(r"(?:文本|Text)\s*[:：]\s*(.+)$", right_side, re.I)
        if text_label_match:
            return text_label_match.group(1).strip(" .。；;")
        if right_side:
            return right_side

    lines = [part.strip() for part in re.split(r"[。；;]", text) if part.strip()]
    clean_lines = [part for part in lines if not _contains_prompt_pollution(part)]
    if clean_lines:
        return clean_lines[-1]

    return line.strip()

def _extract_glossary_terms(things_to_note_prompt):
    if not things_to_note_prompt:
        return []

    terms = []
    for line in str(things_to_note_prompt).splitlines():
        line = line.strip()
        if not line:
            continue

        match = re.search(r'["“]([^"”]+)["”]\s*:\s*["“]?([^",”]+)', line)
        if match:
            src = match.group(1).strip()
            tgt = match.group(2).strip()
            if _should_skip_identity_name_term(src, tgt):
                continue
            terms.append((src, tgt))

    return terms[:20]

def _should_skip_identity_name_term(src, tgt):
    if _normalize_token(src) != _normalize_token(tgt):
        return False
    return bool(re.match(r"^[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+)+$", str(src).strip()))

def _normalize_token(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())

def _similar(a, b):
    a = _normalize_token(a)
    b = _normalize_token(b)
    if not a or not b:
        return 0
    return SequenceMatcher(None, a, b).ratio()

def _line_matches_term(line, src):
    if src.lower() in line.lower():
        return True
    line_words = re.findall(r"[A-Za-z][A-Za-z'’-]*", line)
    term_parts = re.findall(r"[A-Za-z][A-Za-z'’-]*", src)
    for part in term_parts:
        if len(part) < 3:
            continue
        for word in line_words:
            if abs(len(word) - len(part)) > 2:
                continue
            if _similar(word, part) >= 0.72:
                return True
    return False

def _format_line_terms(line, glossary_terms):
    matched_terms = []
    for src, tgt in glossary_terms:
        if _line_matches_term(line, src):
            matched_terms.append(f"{src} = {tgt} (normalize similar ASR spellings to this exact proper noun/term)")
    return "\n".join(matched_terms)

PROPER_NAME_SOURCE_RE = re.compile(r"\b[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+)+\b")
TRANSLATED_NAME_RE = re.compile(r"[\u3400-\u9fff]+(?:·[\u3400-\u9fff]+)+")

def _source_proper_names(source):
    names = []
    for match in PROPER_NAME_SOURCE_RE.finditer(str(source)):
        name = match.group(0).strip()
        if name.lower() in {"60 minutes"}:
            continue
        names.append(name)
    return names

def _name_translation_map(source_lines, translations):
    name_map = {}
    for source, translation in zip(source_lines, translations):
        source_names = _source_proper_names(source)
        translated_names = TRANSLATED_NAME_RE.findall(str(translation))
        if not source_names or not translated_names:
            continue
        for source_name, translated_name in zip(source_names, translated_names):
            if source_name not in str(translation):
                name_map.setdefault(source_name, translated_name)
    return name_map

def _apply_name_translation_map(text, name_map):
    normalized = str(text)
    for source_name, translated_name in sorted(name_map.items(), key=lambda item: len(item[0]), reverse=True):
        normalized = re.sub(rf"\b{re.escape(source_name)}\b", translated_name, normalized)
        normalized = re.sub(rf"(?<=[\u3400-\u9fff……？！。，、；：])\s+{re.escape(translated_name)}", translated_name, normalized)
    return normalize_cjk_latin_spacing(normalized)

def _normalize_proper_name_translations(source_lines, translations, reference_translations=None):
    references = list(reference_translations or []) + list(translations)
    repeated_sources = list(source_lines) * (2 if reference_translations else 1)
    name_map = _name_translation_map(repeated_sources, references)
    if not name_map:
        return translations
    return [_apply_name_translation_map(translation, name_map) for translation in translations]

def _translate_line_with_translator(line, target_language, line_terms=None):
    # For local translators: split multi-sentence lines to prevent the model
    # from dropping short lead sentences (e.g. "Thank you.", "It's astounding.")
    if is_local_translator():
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', str(line).strip()) if s.strip()]
        if len(sentences) >= 2:
            translations = []
            for sent in sentences:
                terms = _format_line_terms(sent, line_terms) if line_terms else None
                terms_block = ("\nTerms:\n" + terms + "\n") if terms else ""
                prompt = f"Translate to {target_language}:\n{sent}"
                last_result = ""
                import time as _time2
                for retry2 in range(3):
                    if retry2 > 0:
                        _time2.sleep(2 * retry2)
                    result = ask_gpt(prompt, resp_type=None, log_title="translate_sentence", api_role="translator")
                    if not result or not str(result).strip():
                        continue
                    cleaned = _clean_translator_output(result)
                    last_result = cleaned
                    if cleaned and not _contains_prompt_pollution(cleaned):
                        translations.append(normalize_cjk_latin_spacing(_remove_filler_words(cleaned)))
                        break
                else:
                    salvaged = _salvage_translator_output(last_result, sent)
                    translations.append(normalize_cjk_latin_spacing(_remove_filler_words(salvaged)))
            return ' '.join(translations)

    terms = (
        "\nTerms:\n"
        f"{line_terms}\n"
        if line_terms else ""
    )
    if is_local_translator():
        # Local models need minimal prompts — they tend to echo instructions
        prompt = f"Translate to {target_language}. Translate completely, do not skip any part:\n{line}"
    else:
        prompt = (
            f"Translate this English subtitle to {target_language}. Reply with ONLY the translation, nothing else.\n"
            f"{terms}Text: {line}"
        )
    last_result = ""
    import time as _time
    for retry in range(3):
        if retry > 0:
            _time.sleep(2 * retry)
        result = ask_gpt(prompt, resp_type=None, log_title="translate_plain", api_role="translator")
        if not result or not str(result).strip():
            console.print(f"[yellow]⚠️ Translator returned empty, retry {retry+1}/3 for: {line[:50]}[/yellow]")
            continue
        cleaned = _clean_translator_output(result)
        last_result = cleaned
        if cleaned and not _contains_prompt_pollution(cleaned):
            return normalize_cjk_latin_spacing(_remove_filler_words(cleaned))
        salvaged = _salvage_translator_output(cleaned, line)
        if salvaged and not _contains_prompt_pollution(salvaged):
            console.print(f"[yellow]⚠️ Translator output contained notes; extracted subtitle translation: {salvaged}[/yellow]")
            return normalize_cjk_latin_spacing(_remove_filler_words(salvaged))
        console.print(f"[yellow]⚠️ Translator output contains prompt text, retrying line: {line}[/yellow]")
    fallback = _salvage_translator_output(last_result, line)
    console.print(f"[yellow]⚠️ Translator kept returning notes; using fallback subtitle text: {fallback}[/yellow]")
    return normalize_cjk_latin_spacing(_remove_filler_words(fallback))

def _is_truthy_ambiguity(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "yes", "y", "1", "是", "有")

def _record_ambiguity_items(items):
    items = [item for item in items if item.get("source") and (item.get("ambiguity") or item.get("reason"))]
    if not items:
        return
    os.makedirs(os.path.dirname(_4_3_AMBIGUITY), exist_ok=True)
    with AMBIGUITY_LOCK:
        existing = []
        if os.path.exists(_4_3_AMBIGUITY):
            try:
                with open(_4_3_AMBIGUITY, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = []
        existing.extend(items)
        with open(_4_3_AMBIGUITY, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

def _collect_ambiguity_items(response_data, source_lines, translations, index=0):
    items = []
    for key in [str(i) for i in range(1, len(source_lines) + 1)]:
        item = response_data.get(key, {})
        ambiguity = str(item.get("ambiguity", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if not (_is_truthy_ambiguity(item.get("ambiguous")) or ambiguity or reason):
            continue
        line_index = int(key) - 1
        items.append({
            "block_index": index,
            "line_in_block": int(key),
            "source": source_lines[line_index],
            "translation": translations[line_index] if line_index < len(translations) else str(item.get("free", "")).strip(),
            "ambiguity": ambiguity,
            "reason": reason,
        })
    _record_ambiguity_items(items)


def _translate_batch_with_translator(batch_lines, target_language, glossary_terms):
    """Translate multiple subtitle lines in a single API call for speed."""
    non_empty = [(i, ln.strip()) for i, ln in enumerate(batch_lines) if ln.strip()]
    if not non_empty:
        return [""] * len(batch_lines)

    numbered = [f"{i+1}: {text}" for i, text in non_empty]
    batch_text = "\n".join(numbered)

    if is_local_translator():
        prompt = (
            f"Translate each numbered line to {target_language}. "
            f"Do not skip any words or sentences — translate ALL content in every line. "
            f"Return one translation per line, same number.\n\n"
            + batch_text
        )
    else:
        prompt = (
            f"Translate each numbered line into {target_language}. "
            f"Return one translation per line, same number prefix.\n"
            f"Output ONLY the translation.\n\n"
            + batch_text
        )

    import time as _time
    for retry in range(3):
        if retry > 0:
            _time.sleep(2 * retry)
        result = ask_gpt(prompt, resp_type=None, log_title="translate_batch", api_role="translator")
        if not result or not str(result).strip():
            console.print(f"[yellow]⚠️ Batch translation returned empty, retry {retry+1}/3[/yellow]")
            continue
        cleaned = _clean_translator_output(result)
        if _contains_prompt_pollution(cleaned):
            continue

        parsed = {}
        for line in cleaned.split('\n'):
            line = line.strip()
            m = re.match(r'^(\d+)[：:.、)\s]*(.+)', line)
            if m:
                parsed[int(m.group(1))] = m.group(2).strip()

        if len(parsed) >= len(non_empty) * 0.8:
            out = [""] * len(batch_lines)
            for i, text in non_empty:
                if (i + 1) in parsed:
                    translated = parsed[i + 1]
                    if translated:
                        out[i] = normalize_cjk_latin_spacing(_remove_filler_words(translated))
            # Retry any lines that came back empty from the batch
            for i, text in non_empty:
                if not out[i]:
                    console.print(f"[yellow]⚠️ Batch translation missed line {i+1}, retrying individually: {text[:50]}[/yellow]")
                    terms = _format_line_terms(text, glossary_terms)
                    out[i] = _translate_line_with_translator(text, target_language, terms)

            # Detect content shifting across adjacent lines (Whisper split sentences)
            for i in range(len(out) - 1):
                if not out[i] or not out[i+1] or not batch_lines[i].strip() or not batch_lines[i+1].strip():
                    continue
                src_i = batch_lines[i].strip()
                src_next = batch_lines[i+1].strip()
                # Sentence split across entries: source[i] ends with comma, source[i+1] starts lowercase
                is_split = bool(
                    re.search(r',\s*$', src_i) and
                    re.match(r'^[a-z]', src_next)
                )
                if not is_split:
                    continue
                # Compare line-length proportions: if source[i] is a short fragment but its
                # translation grabbed content from the next line, the proportion flips
                total_src = len(src_i) + len(src_next)
                total_trans = len(out[i]) + len(out[i+1])
                if total_trans == 0:
                    continue
                src_share = len(src_i) / total_src    # e.g. 52/222 = 23%
                trans_share = len(out[i]) / total_trans  # e.g. 38/67 = 57%
                # Fragment source got disproportionately long translation => content shifted
                if src_share < 0.35 and trans_share > 0.45:
                    console.print(
                        f"[yellow]\u26a0\ufe0f Detected content shift in batch: source line {i+1} "
                        f"is {src_share:.0%} of pair ({len(src_i)}/{total_src} chars) but its "
                        f"translation is {trans_share:.0%} of pair ({len(out[i])}/{total_trans} chars). "
                        f"Re-translating lines {i+1},{i+2} individually.[/yellow]"
                    )
                    terms_i = _format_line_terms(src_i, glossary_terms)
                    terms_next = _format_line_terms(src_next, glossary_terms)
                    out[i] = _translate_line_with_translator(src_i, target_language, terms_i)
                    out[i+1] = _translate_line_with_translator(src_next, target_language, terms_next)

            # Detect dropped content: translation unreasonably short for its source
            for i, text in non_empty:
                src_len = len(batch_lines[i].strip())
                trans_len = len(out[i]) if out[i] else 0
                # Skip very short source lines (< 20 chars) — short is normal for those
                if src_len < 20 or trans_len == 0:
                    continue
                # Chinese compresses English by roughly 40-60%. If translation is
                # under 20% of source length, content was likely dropped entirely.
                if trans_len < src_len * 0.2:
                    console.print(
                        f"[yellow]\u26a0\ufe0f Content may be dropped: line {i+1} source "
                        f"({src_len} chars) translated to only {trans_len} chars. "
                        f"Re-translating individually.[/yellow]"
                    )
                    terms = _format_line_terms(batch_lines[i].strip(), glossary_terms)
                    out[i] = _translate_line_with_translator(
                        batch_lines[i].strip(), target_language, terms
                    )

            return out

    # Fallback: line by line
    results = []
    for line in batch_lines:
        clean = line.strip()
        if not clean:
            results.append("")
            continue
        terms = _format_line_terms(clean, glossary_terms)
        results.append(_translate_line_with_translator(clean, target_language, terms))
    return results

def _translate_lines_with_translator(lines, things_to_note_prompt=None, summary_prompt=None, index=0):
    summary_prompt = _with_video_description(summary_prompt)
    target_language = load_key("target_language")
    glossary_terms = _extract_glossary_terms(things_to_note_prompt)
    source_lines = lines.split('\n')
    translations = []
    BATCH_SIZE = 1 if is_local_translator() else 6
    for batch_start in range(0, len(source_lines), BATCH_SIZE):
        batch = source_lines[batch_start:batch_start + BATCH_SIZE]
        translations.extend(_translate_batch_with_translator(batch, target_language, glossary_terms))
    translations = translations[:len(source_lines)]
    while len(translations) < len(source_lines):
        translations.append("")
    raw_translations = translations[:]

    table = Table(title="Translation Model Results", show_header=False, box=box.ROUNDED)
    table.add_column("Translations", style="bold")
    for i, (origin, translation) in enumerate(zip(source_lines, translations)):
        table.add_row(f"[cyan]Origin:  {origin}[/cyan]")
        table.add_row(f"[green]Target:  {translation}[/green]")
        if i < len(source_lines) - 1:
            table.add_row("[yellow]" + "-" * 50 + "[/yellow]")
    console.print(table)

    translate_result = "\n".join(translations)
    if len(source_lines) != len(translate_result.split('\n')):
        raise ValueError(f'Hy-MT2 translation line count mismatch in block {index}')

    use_workflow_refine = _load_bool("reflect_translate") and _load_bool("translator_refine_with_workflow", True)
    if use_workflow_refine:
        try:
            shared_prompt = generate_shared_prompt(None, None, summary_prompt, things_to_note_prompt)
            translate_result = _refine_translator_result(lines, translate_result, shared_prompt, index)
        except Exception as e:
            console.print(f'[yellow]⚠️ Workflow refinement failed for block {index}; using translator output: {e}[/yellow]')
    elif _load_bool('enable_ambiguity_check'):
        # Collect ambiguity via expressiveness prompt on already-translated lines
        try:
            _collect_ambiguity_for_translator_result(
                lines, translate_result,
                generate_shared_prompt(None, None, summary_prompt, things_to_note_prompt),
                index
            )
        except Exception as e:
            console.print(f'[yellow]⚠️ Ambiguity check for block {index} failed (non-fatal): {e}[/yellow]')

    final_translations = translate_result.split('\n')
    final_translations = _finalize_translations_after_refine(
        source_lines,
        final_translations,
        raw_translations,
        target_language,
        glossary_terms,
    )
    final_translations = _normalize_proper_name_translations(source_lines, final_translations, raw_translations)
    translate_result = "\n".join(final_translations)

    return translate_result, lines

def _collect_ambiguity_for_translator_result(lines, translate_result, shared_prompt, index=0):
    """Run expressiveness prompt on translator output to collect ambiguity, without modifying translations."""
    source_lines = lines.split('\n')
    translations_list = translate_result.split('\n')

    faith_result = {}
    for j, (src, trans) in enumerate(zip(source_lines, translations_list), 1):
        faith_result[str(j)] = {"origin": src, "direct": trans}

    prompt = get_prompt_expressiveness(faith_result, lines, shared_prompt)

    def valid_express(response_data):
        required_keys = [str(k) for k in range(1, len(source_lines) + 1)]
        return valid_translate_result(response_data, required_keys, ['free'])

    for retry in range(2):
        result = ask_gpt(prompt + " " * retry, resp_type='json',
                         valid_def=valid_express, log_title='ambiguity_collect', api_role='workflow')
        if len(result) == len(source_lines):
            _collect_ambiguity_items(result, source_lines, translations_list, index)
            return
    console.print(f'[yellow]⚠️ Ambiguity check for block {index} failed to get valid response.[/yellow]')

def _refine_translator_result(lines, direct_translations, shared_prompt, index=0):
    source_lines = lines.split('\n')
    prompt = get_prompt_refine_translator_result(lines, direct_translations, shared_prompt)

    def valid_refine(response_data):
        required_keys = [str(i) for i in range(1, len(source_lines) + 1)]
        return valid_translate_result(response_data, required_keys, ['free'])

    for retry in range(3):
        result = ask_gpt(prompt + " " * retry, resp_type='json', valid_def=valid_refine, log_title='translate_refine', api_role='workflow')
        if len(result) == len(source_lines):
            refined = []
            for key in [str(i) for i in range(1, len(source_lines) + 1)]:
                free_text = str(result[key]['free']).replace('\n', ' ').strip()
                refined.append(normalize_cjk_latin_spacing(_remove_filler_words(_salvage_translator_output(free_text, source_lines[int(key) - 1]))))
            translate_result = "\n".join(refined)
            if len(source_lines) == len(translate_result.split('\n')):
                if _load_bool('enable_ambiguity_check'):
                    _collect_ambiguity_items(result, source_lines, translate_result.split('\n'), index)
                return translate_result
        console.print(f'[yellow]⚠️ Translation refinement of block {index} failed, retrying...[/yellow]')

    console.print(f'[yellow]⚠️ Translation refinement of block {index} failed; using direct translator output.[/yellow]')
    return direct_translations

def valid_translate_result(result: dict, required_keys: list, required_sub_keys: list):
    # Check for the required key
    if not all(key in result for key in required_keys):
        return {"status": "error", "message": f"Missing required key(s): {', '.join(set(required_keys) - set(result.keys()))}"}
    
    # Check for required sub-keys in all items
    for key in result:
        if not all(sub_key in result[key] for sub_key in required_sub_keys):
            return {"status": "error", "message": f"Missing required sub-key(s) in item {key}: {', '.join(set(required_sub_keys) - set(result[key].keys()))}"}

    return {"status": "success", "message": "Translation completed"}

def translate_lines(lines, previous_content_prompt, after_cotent_prompt, things_to_note_prompt, summary_prompt, index = 0):
    summary_prompt = _with_video_description(summary_prompt)
    # Only use batch/line-by-line path for local translator models (e.g. translategemma via llama.cpp).
    # Remote LLMs (DeepSeek, OpenAI, etc.) go through the reliable 2-step JSON pipeline.
    if _has_translator_model() and not is_remote_translator() and _local_translator_available():
        try:
            return _translate_lines_with_translator(lines, things_to_note_prompt, summary_prompt, index)
        except Exception as e:
            console.print(f"[yellow]⚠️ Local translator failed for block {index}: {e}[/yellow]")
            console.print("[yellow]   Falling back to workflow model for this block...[/yellow]")

    shared_prompt = generate_shared_prompt(previous_content_prompt, after_cotent_prompt, summary_prompt, things_to_note_prompt)

    # Retry translation if the length of the original text and the translated text are not the same, or if the specified key is missing
    def retry_translation(prompt, length, step_name):
        def valid_faith(response_data):
            return valid_translate_result(response_data, [str(i) for i in range(1, length+1)], ['direct'])
        def valid_express(response_data):
            return valid_translate_result(response_data, [str(i) for i in range(1, length+1)], ['free'])
        for retry in range(3):
            if step_name == 'faithfulness':
                result = ask_gpt(prompt+retry* " ", resp_type='json', valid_def=valid_faith, log_title=f'translate_{step_name}')
            elif step_name == 'expressiveness':
                result = ask_gpt(prompt+retry* " ", resp_type='json', valid_def=valid_express, log_title=f'translate_{step_name}')
            if len(lines.split('\n')) == len(result):
                return result
            if retry == 0:
                console.print(f'[yellow]⚠️ {step_name.capitalize()} translation of block {index} failed, Retry...[/yellow]')
        raise ValueError(f'[red]❌ {step_name.capitalize()} translation of block {index} failed after 3 retries. Please check `output/gpt_log/error.json` for more details.[/red]')

    ## Step 1: Faithful to the Original Text
    prompt1 = get_prompt_faithfulness(lines, shared_prompt)
    faith_result = retry_translation(prompt1, len(lines.split('\n')), 'faithfulness')

    for i in faith_result:
        faith_result[i]["direct"] = faith_result[i]["direct"].replace('\n', ' ')

    # If reflect_translate is False or not set, use faithful translation directly
    reflect_translate = load_key('reflect_translate')
    if not reflect_translate:
        # If reflect_translate is False or not set, use faithful translation directly
        direct_translations = [normalize_cjk_latin_spacing(faith_result[i]["direct"].strip()) for i in faith_result]
        translate_result = "\n".join(_normalize_proper_name_translations(lines.split('\n'), direct_translations))
        
        table = Table(title="Translation Results", show_header=False, box=box.ROUNDED)
        table.add_column("Translations", style="bold")
        for i, key in enumerate(faith_result):
            table.add_row(f"[cyan]Origin:  {faith_result[key]['origin']}[/cyan]")
            table.add_row(f"[magenta]Direct:  {faith_result[key]['direct']}[/magenta]")
            if i < len(faith_result) - 1:
                table.add_row("[yellow]" + "-" * 50 + "[/yellow]")
        
        console.print(table)
        return translate_result, lines

    ## Step 2: Express Smoothly  
    prompt2 = get_prompt_expressiveness(faith_result, lines, shared_prompt)
    express_result = retry_translation(prompt2, len(lines.split('\n')), 'expressiveness')

    table = Table(title="Translation Results", show_header=False, box=box.ROUNDED)
    table.add_column("Translations", style="bold")
    for i, key in enumerate(express_result):
        table.add_row(f"[cyan]Origin:  {faith_result[key]['origin']}[/cyan]")
        table.add_row(f"[magenta]Direct:  {faith_result[key]['direct']}[/magenta]")
        table.add_row(f"[green]Free:    {express_result[key]['free']}[/green]")
        if i < len(express_result) - 1:
            table.add_row("[yellow]" + "-" * 50 + "[/yellow]")

    console.print(table)

    direct_translations = [normalize_cjk_latin_spacing(faith_result[i]["direct"].strip()) for i in faith_result]
    free_translations = [normalize_cjk_latin_spacing(express_result[i]["free"].replace('\n', ' ').strip()) for i in express_result]
    translate_result = "\n".join(_normalize_proper_name_translations(lines.split('\n'), free_translations, direct_translations))
    _collect_ambiguity_items(express_result, lines.split('\n'), translate_result.split('\n'), index)

    if len(lines.split('\n')) != len(translate_result.split('\n')):
        console.print(Panel(f'[red]❌ Translation of block {index} failed, Length Mismatch, Please check `output/gpt_log/translate_expressiveness.json`[/red]'))
        raise ValueError(f'Origin ···{lines}···,\nbut got ···{translate_result}···')

    return translate_result, lines

def generate_ambiguity_report_standalone():
    """Generate an ambiguity report from already-translated subtitles.

    Reads the translation Excel file, chunks source+translation pairs the same way
    the original pipeline does, then runs each chunk through the workflow model's
    expressiveness prompt to detect ambiguous words/phrases.

    Safe to call during the subtitle translation pipeline (clears and regenerates
    the report each time).
    """
    import pandas as pd
    from core.utils.models import _4_2_TRANSLATION, _3_2_SPLIT_BY_MEANING, _4_3_AMBIGUITY as AMBIGUITY_PATH
    from core._4_2_translate import split_chunks_by_chars

    if not os.path.exists(_4_2_TRANSLATION):
        console.print("[red]❌ No translation results found. Run subtitle translation first.[/red]")
        print("AMBIGUITY_ERROR: no_translation_file", file=sys.stderr)
        return False

    if not os.path.exists(_3_2_SPLIT_BY_MEANING):
        console.print("[red]❌ No split source text found. Run subtitle processing first.[/red]")
        print("AMBIGUITY_ERROR: no_split_file", file=sys.stderr)
        return False

    # Clear existing ambiguity report
    if os.path.exists(AMBIGUITY_PATH):
        os.remove(AMBIGUITY_PATH)

    # Read translated lines
    try:
        df = pd.read_excel(_4_2_TRANSLATION)
    except Exception as e:
        console.print(f"[red]❌ Failed to read translation file: {e}[/red]")
        print(f"AMBIGUITY_ERROR: excel_read_failed: {e}", file=sys.stderr)
        return False

    translations = df['Translation'].tolist()
    if not translations:
        console.print("[red]❌ No translation lines to check.[/red]")
        print("AMBIGUITY_ERROR: empty_data", file=sys.stderr)
        return False

    # Chunk into blocks using the same logic as the original pipeline.
    # split_chunks_by_chars reads _3_2_SPLIT_BY_MEANING and returns grouped text blocks.
    chunks = split_chunks_by_chars(chunk_size=600, max_i=10)
    total_blocks = len(chunks)
    trans_idx = 0

    console.print(f"[cyan]Running ambiguity check on {total_blocks} blocks ({len(translations)} translations)...[/cyan]")

    for block_index, chunk_text in enumerate(chunks):
        chunk_lines = chunk_text.strip().split('\n')
        if not chunk_lines:
            continue

        N = len(chunk_lines)
        block_source = chunk_lines
        block_trans = translations[trans_idx:trans_idx + N]
        trans_idx += N

        if not block_source or trans_idx > len(translations):
            continue

        # Construct fake faith_result from source lines and existing translations
        faith_result = {}
        for j, (src, trans) in enumerate(zip(block_source, block_trans), 1):
            faith_result[str(j)] = {"origin": src, "direct": trans}

        shared_prompt = generate_shared_prompt(None, None, "", "")
        prompt = get_prompt_expressiveness(faith_result, '\n'.join(block_source), shared_prompt)

        def valid_express(response_data):
            required_keys = [str(k) for k in range(1, len(block_source) + 1)]
            return valid_translate_result(response_data, required_keys, ['free'])

        for retry in range(2):
            try:
                result = ask_gpt(prompt + " " * retry, resp_type='json',
                                 valid_def=valid_express, log_title='ambiguity_standalone',
                                 api_role='workflow')
                if len(result) == len(block_source):
                    _collect_ambiguity_items(result, block_source, block_trans, block_index)
                    break
            except Exception as e:
                console.print(f'[yellow]⚠️ Standalone ambiguity check block {block_index} attempt {retry+1} failed: {e}[/yellow]')
        else:
            console.print(f'[yellow]⚠️ Standalone ambiguity check block {block_index} failed after retries.[/yellow]')

    console.print(f"[bold green]✅ Ambiguity report generated: {AMBIGUITY_PATH}[/bold green]")
    return True


if __name__ == '__main__':
    # test e.g.
    lines = '''All of you know Andrew Ng as a famous computer science professor at Stanford.
He was really early on in the development of neural networks with GPUs.
Of course, a creator of Coursera and popular courses like deeplearning.ai.
Also the founder and creator and early lead of Google Brain.'''
    previous_content_prompt = None
    after_cotent_prompt = None
    things_to_note_prompt = None
    summary_prompt = None
    translate_lines(lines, previous_content_prompt, after_cotent_prompt, things_to_note_prompt, summary_prompt)
