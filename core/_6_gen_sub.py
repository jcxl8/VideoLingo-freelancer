import pandas as pd
import os
import re
import json
import cv2
from difflib import SequenceMatcher
from rich.panel import Panel
from rich.console import Console
import autocorrect_py as autocorrect
from core.utils import *
from core.utils.models import *
from core._1_ytdlp import find_video_files
from core._7_sub_into_vid import (
    _is_portrait_video,
    _portrait_font_sizes,
    _portrait_safe_side_margin,
    get_default_subtitle_paths,
)
from core.asr_backend.audio_preprocess import (
    _near_duplicate_content_mask,
    _near_duplicate_subtoken_mask,
)
from core.subtitle_proofread import (
    SUBTITLE_PROOFREAD_REPORT_JSON,
    SUBTITLE_PROOFREAD_REPORT_MD,
    clear_subtitle_proofread_report,
    proofread_subtitle_set,
)
console = Console()
AMBIGUITY_REPORT_MD = "output/ambiguity_report.md"
SUBTITLE_TIMING_REPORT_JSON = "output/log/subtitle_timing_quality.json"
SUBTITLE_TIMING_REPORT_MD = "output/log/subtitle_timing_quality.md"
SUBTITLE_GAP_FILL_MAX_SECONDS = 0.12
SUBTITLE_MAX_OVERLAP_SECONDS = 0.08
SUBTITLE_MIN_DURATION_SECONDS = 0.08
SUBTITLE_BOUNDARY_WORD_MAX_DURATION_SECONDS = 1.2
SUBTITLE_DISPLAY_TAIL_SECONDS = 0.25
SUBTITLE_NEXT_START_GUARD_SECONDS = 0.04
SUBTITLE_MAX_SAFE_EXTENSION_SECONDS = 1.6
SUBTITLE_LONG_SILENCE_EXTENSION_THRESHOLD_SECONDS = 1.2
SUBTITLE_LONG_SILENCE_MAX_EXTENSION_SECONDS = 4.0
SUBTITLE_LONG_SILENCE_NEXT_GUARD_SECONDS = 0.12
SUBTITLE_MIN_READABLE_SECONDS = 1.25
SUBTITLE_MAX_SOURCE_CPS = 18.0
SUBTITLE_MAX_SOURCE_WPS = 3.2
SUBTITLE_MAX_TRANSLATION_CPS = 11.0
SUBTITLE_MAX_BILINGUAL_CPS = 22.0
SUBTITLE_SHORT_MERGE_MAX_GAP_SECONDS = 0.35
SUBTITLE_CONTINUATION_MERGE_MAX_GAP_SECONDS = 0.8
SUBTITLE_MERGE_MAX_SOURCE_WORDS = 22
SUBTITLE_MERGE_MAX_SOURCE_CHARS = 110
SUBTITLE_MERGE_MAX_TRANSLATION_CHARS = 95
SUBTITLE_MERGE_MAX_DURATION_SECONDS = 8.0
SOURCE_ARTIFACT_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*\.?")
LATIN_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?")
LEADING_SOURCE_PUNCT_RE = re.compile(r"^\s*[,.;:!?，。；：！？]+\s*")
CONTINUATION_START_RE = re.compile(
    r"^\s*(?:[,.;:!?，。；：！？]+|"
    r"(?:a|an|the|of|to|in|on|at|by|for|from|with|without|and|or|but|so|as|if|when|while|although|because|that|which|who|where|not|then|well|now|also|just|only|even|still|yet|it|he|she|they|we|you|i|my|your|his|her|their|our|this|these|those|there|here|what|how|why)\b)",
    re.I,
)
LANGUAGE_LABEL_RE = re.compile(
    r"^\s*(?:简体中文|繁體中文|中文|英文|英语|译文|翻译|转译为简体中文|翻译为简体中文|翻译成简体中文|Translation|Target(?:\s+Language)?)\s*[:：]\s*",
    re.I,
)
NONREPEATABLE_DUPLICATE_SOURCE_WORDS = {
    "a", "an", "the",
    "of", "to", "in", "on", "at", "by", "for", "from", "with", "without",
}
NONREPEATABLE_DUPLICATE_SOURCE_RE = re.compile(
    r"\b("
    + "|".join(sorted(map(re.escape, NONREPEATABLE_DUPLICATE_SOURCE_WORDS), key=len, reverse=True))
    + r")\b(?:\s+\1\b)+",
    re.I,
)
ASR_SOURCE_PHRASE_CORRECTIONS = [
    (re.compile(r"\bwon\s+wanted\b", re.I), "wanted"),
    (re.compile(r"\bnational\s+all\b", re.I), "National Mall"),
    (re.compile(r"\bAfrica[\s.]+Americans\b", re.I), "African Americans"),
]
PROGRAM_BREAK_SOURCE_RE = re.compile(
    r"\b(?:will\s+continue\s+in\s+a\s+moment|we(?:'|’)ll\s+be\s+right\s+back|"
    r"coming\s+up|after\s+the\s+break)\b",
    re.I,
)

SUBTITLE_OUTPUT_CONFIG_KEYS = [
    ('src', ['Source']),
    ('trans', ['Translation']),
    ('src_trans', ['Source', 'Translation']),
    ('trans_src', ['Translation', 'Source'])
]

AUDIO_SUBTITLE_OUTPUT_CONFIGS = [
    ('src_subs_for_audio.srt', ['Source']),
    ('trans_subs_for_audio.srt', ['Translation'])
]

LEADING_ACK_RE = re.compile(
    r"^\s*(?:thank\s+you(?:\s+very\s+much)?|thanks|thank\s+you\s+so\s+much)"
    r"[\s,.;:!?，。；：！？]+",
    re.I,
)
LEADING_TRANSLATION_ACK_RE = re.compile(
    r"^\s*(?:谢谢|多谢|感谢|非常感谢|十分感谢|谢谢你|谢谢您)"
    r"[\s,.;:!?，。；：！？]*"
)
STANDALONE_ACK_SOURCE_RE = re.compile(
    r"^\s*(?:thank\s+you(?:\s+very\s+much|\s+so\s+much)?|thanks|thank\s+you\s+again)"
    r"\s*[.!?。！？]?\s*$",
    re.I,
)
STANDALONE_ACK_TRANSLATION_RE = re.compile(
    r"^\s*(?:谢谢|多谢|感谢|非常感谢|十分感谢|谢谢你|谢谢您)"
    r"\s*[.!?。！？]?\s*$"
)
SHORT_ANSWER_SOURCE_RE = re.compile(
    r"^\s*(?:probably|maybe|yes|yeah|yep|no|nope|sure|absolutely|right|okay|ok|exactly|certainly)"
    r"(?:\s+\w+)?\s*[.!?。！？]?\s*$",
    re.I,
)

def convert_to_srt_format(start_time, end_time):
    """Convert time (in seconds) to the format: hours:minutes:seconds,milliseconds"""
    def seconds_to_hmsm(seconds):
        total_milliseconds = int(round(float(seconds) * 1000))
        hours, remainder = divmod(total_milliseconds, 3600 * 1000)
        minutes, remainder = divmod(remainder, 60 * 1000)
        seconds, milliseconds = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"

    start_srt = seconds_to_hmsm(start_time)
    end_srt = seconds_to_hmsm(end_time)
    return f"{start_srt} --> {end_srt}"

def remove_punctuation(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()

def _clean_word_token(text):
    return remove_punctuation(str(text).lower()).strip()

def _contextual_word_artifact_mask(df_words):
    if df_words.empty or "text" not in df_words.columns:
        return pd.Series(False, index=df_words.index, dtype=bool)

    tokens = [_clean_word_token(word) for word in df_words["text"]]
    duplicate_mask = []
    for index, token in enumerate(tokens):
        next_token = tokens[index + 1] if index + 1 < len(tokens) else ""
        duplicate_mask.append(token == "won" and next_token == "wanted")
    return pd.Series(duplicate_mask, index=df_words.index, dtype=bool)

def _apply_contextual_word_corrections(df_words):
    if df_words.empty or "text" not in df_words.columns:
        return df_words

    df_words = df_words.copy()
    tokens = [_clean_word_token(word) for word in df_words["text"]]
    corrected_count = 0
    for index, token in enumerate(tokens):
        previous_token = tokens[index - 1] if index > 0 else ""
        if previous_token == "national" and token == "all":
            df_words.at[df_words.index[index], "text"] = "Mall"
            corrected_count += 1
        next_token = tokens[index + 1] if index + 1 < len(tokens) else ""
        if token == "africa" and next_token == "americans":
            df_words.at[df_words.index[index], "text"] = "African"
            corrected_count += 1
    if corrected_count:
        console.print(f"[blue]ℹ️ Corrected {corrected_count} contextual ASR word(s) before timestamp alignment.[/blue]")
    return df_words

def _nonrepeatable_word_duplicate_mask(df_words):
    if df_words.empty or "text" not in df_words.columns:
        return pd.Series(False, index=df_words.index, dtype=bool)

    duplicate_mask = []
    previous_token = ""
    for word in df_words["text"]:
        current_token = _clean_word_token(word)
        duplicate_mask.append(
            bool(current_token)
            and current_token == previous_token
            and current_token in NONREPEATABLE_DUPLICATE_SOURCE_WORDS
        )
        previous_token = current_token
    return pd.Series(duplicate_mask, index=df_words.index, dtype=bool)

def _clean_df_text_asr_artifacts(df_words):
    df_words = _apply_contextual_word_corrections(df_words)
    duplicate_mask = (
        _near_duplicate_content_mask(df_words)
        | _near_duplicate_subtoken_mask(df_words)
        | _nonrepeatable_word_duplicate_mask(df_words)
        | _contextual_word_artifact_mask(df_words)
    )
    duplicate_count = int(duplicate_mask.sum())
    if duplicate_count:
        removed_words = ", ".join(
            str(word) for word in df_words.loc[duplicate_mask, "text"].head(5).tolist()
        )
        df_words = df_words[~duplicate_mask].copy().reset_index(drop=True)
        console.print(
            f"[blue]ℹ️ Removed {duplicate_count} ASR duplicate artifact(s) before timestamp alignment: "
            f"{removed_words}[/blue]"
        )
    return df_words

def _first_source_token(text):
    match = SOURCE_ARTIFACT_TOKEN_RE.search(str(text).strip())
    return match.group(0).strip(".") if match else ""

def _last_source_token(text):
    matches = SOURCE_ARTIFACT_TOKEN_RE.findall(str(text))
    return matches[-1].strip(".") if matches else ""

def _is_suffix_artifact(previous_token, current_token):
    previous = _clean_word_token(previous_token)
    current = _clean_word_token(current_token)
    return (
        len(current) >= 4
        and len(previous) >= len(current) + 3
        and previous.endswith(current)
    )

def _remove_leading_source_token(text):
    return SOURCE_ARTIFACT_TOKEN_RE.sub("", str(text), count=1).lstrip(" \t,.;:，。；：")

def _remove_duplicate_leading_source_token(text):
    match = re.match(
        r"^\s*[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*\.?\s*([,;:，；：])?\s*(.*)$",
        str(text),
    )
    if not match:
        return _remove_leading_source_token(text)
    punctuation = match.group(1) or ""
    rest = match.group(2).strip()
    return re.sub(r"\s+", " ", f"{punctuation} {rest}" if punctuation else rest).strip()

def _collapse_nonrepeatable_source_words(text):
    return NONREPEATABLE_DUPLICATE_SOURCE_RE.sub(lambda match: match.group(1), str(text))

def _apply_source_phrase_corrections(text):
    corrected = str(text)
    for pattern, replacement in ASR_SOURCE_PHRASE_CORRECTIONS:
        corrected = pattern.sub(replacement, corrected)
    return corrected

def _remove_leading_translation_artifact(text, token):
    escaped = re.escape(str(token).strip())
    if not escaped:
        return text
    return re.sub(
        rf"^\s*{escaped}\s*[:：,，.;；。-]*\s*",
        "",
        str(text),
        count=1,
        flags=re.I,
    )

def _clean_source_boundary_text(text):
    cleaned = LEADING_SOURCE_PUNCT_RE.sub("", str(text)).strip()
    cleaned = _collapse_nonrepeatable_source_words(cleaned)
    return _apply_source_phrase_corrections(cleaned)

def _clean_translation_boundary_text(text):
    return LANGUAGE_LABEL_RE.sub("", str(text)).strip()

def _starts_with_lowercase_latin(text):
    cleaned = LEADING_SOURCE_PUNCT_RE.sub("", str(text or "")).lstrip()
    match = re.match(r"[A-Za-z]", cleaned)
    return bool(match and match.group(0).islower())

def _is_continuation_start(text):
    cleaned = str(text or "").strip()
    return bool(CONTINUATION_START_RE.match(cleaned) or _starts_with_lowercase_latin(cleaned))

def _same_boundary_token(previous_source, current_source):
    previous_token = _clean_word_token(_last_source_token(previous_source))
    current_token = _clean_word_token(_first_source_token(current_source))
    return bool(previous_token and previous_token == current_token)

def _clean_sentence_source_artifacts(df_sentences):
    if df_sentences.empty or "Source" not in df_sentences.columns:
        return df_sentences

    df_sentences = df_sentences.copy()
    for row_idx in range(len(df_sentences)):
        cleaned_source = _clean_source_boundary_text(df_sentences.at[row_idx, "Source"])
        if cleaned_source:
            df_sentences.at[row_idx, "Source"] = cleaned_source
        if "Translation" in df_sentences.columns:
            df_sentences.at[row_idx, "Translation"] = _clean_translation_boundary_text(
                df_sentences.at[row_idx, "Translation"]
            )

    removed_count = 0
    for row_idx in range(1, len(df_sentences)):
        previous_source = df_sentences.at[row_idx - 1, "Source"]
        current_source = df_sentences.at[row_idx, "Source"]
        previous_token = _last_source_token(previous_source)
        current_token = _first_source_token(current_source)
        is_duplicate_boundary = (
            _is_continuation_start(current_source)
            and _same_boundary_token(previous_source, current_source)
        )
        if not (_is_suffix_artifact(previous_token, current_token) or is_duplicate_boundary):
            continue

        cleaned_source = (
            _remove_duplicate_leading_source_token(current_source)
            if is_duplicate_boundary
            else _remove_leading_source_token(current_source)
        )
        if not cleaned_source:
            continue
        df_sentences.at[row_idx, "Source"] = cleaned_source
        if "Translation" in df_sentences.columns:
            cleaned_translation = _remove_leading_translation_artifact(
                df_sentences.at[row_idx, "Translation"],
                current_token,
            )
            if cleaned_translation:
                df_sentences.at[row_idx, "Translation"] = cleaned_translation
        removed_count += 1

    if removed_count:
        console.print(f"[blue]ℹ️ Removed {removed_count} subtitle source artifact(s) before timestamp alignment.[/blue]")
    return df_sentences

def _word_duration(df_words, word_idx):
    return float(df_words['end'][word_idx]) - float(df_words['start'][word_idx])

def _gap_between_words(df_words, left_idx, right_idx):
    return float(df_words['start'][right_idx]) - float(df_words['end'][left_idx])

def _effective_word_end(df_words, start_word_idx, end_word_idx):
    start = float(df_words['start'][end_word_idx])
    end = float(df_words['end'][end_word_idx])
    if end - start <= 3.0:
        return end

    capped_end = start + SUBTITLE_BOUNDARY_WORD_MAX_DURATION_SECONDS
    if end_word_idx + 1 < len(df_words):
        next_start = float(df_words['start'][end_word_idx + 1])
        if next_start > start:
            capped_end = min(capped_end, max(start + SUBTITLE_MIN_DURATION_SECONDS, next_start - 0.02))
    capped_end = min(capped_end, end)
    console.print(
        f"[yellow]⚠️ Clipped abnormal subtitle boundary word duration at word {end_word_idx + 1}: "
        f"{df_words['text'][end_word_idx]}[/yellow]"
    )
    return capped_end

def _visible_char_count(text):
    return len(re.sub(r"\s+", "", str(text or "")))

def _latin_word_count(text):
    return len(LATIN_WORD_RE.findall(str(text or "")))

def _required_display_duration(row):
    source = str(row.get("Source", ""))
    translation = str(row.get("Translation", ""))
    source_chars = _visible_char_count(source)
    translation_chars = _visible_char_count(translation)
    source_words = _latin_word_count(source)
    visible_total = source_chars + translation_chars

    required = SUBTITLE_MIN_DURATION_SECONDS
    if source_words >= 3 or source_chars >= 10 or translation_chars >= 8:
        required = SUBTITLE_MIN_READABLE_SECONDS
    if source_words:
        required = max(required, source_words / SUBTITLE_MAX_SOURCE_WPS)
    if source_chars:
        required = max(required, source_chars / SUBTITLE_MAX_SOURCE_CPS)
    if translation_chars:
        required = max(required, translation_chars / SUBTITLE_MAX_TRANSLATION_CPS)
    if visible_total and translation_chars:
        required = max(required, visible_total / SUBTITLE_MAX_BILINGUAL_CPS)

    return required

def _is_program_break_subtitle(row):
    source = str(row.get("Source", "") or "")
    translation = str(row.get("Translation", "") or "")
    return bool(PROGRAM_BREAK_SOURCE_RE.search(source) or PROGRAM_BREAK_SOURCE_RE.search(translation))

def _long_silence_display_end(row, speech_end, next_start):
    if next_start is None or _is_program_break_subtitle(row):
        return None

    gap_to_next = float(next_start) - float(speech_end)
    if gap_to_next < SUBTITLE_LONG_SILENCE_EXTENSION_THRESHOLD_SECONDS:
        return None

    source_words = _latin_word_count(row.get("Source", ""))
    source_chars = _visible_char_count(row.get("Source", ""))
    translation_chars = _visible_char_count(row.get("Translation", ""))
    if source_words < 5 and source_chars < 18 and translation_chars < 10:
        return None

    return min(
        float(speech_end) + SUBTITLE_LONG_SILENCE_MAX_EXTENSION_SECONDS,
        float(next_start) - SUBTITLE_LONG_SILENCE_NEXT_GUARD_SECONDS,
    )

def _timestamp_dict_to_tuple(time_info):
    return (float(time_info["speech_start"]), float(time_info["speech_end"]))

def _format_timestamp_range(start_time, end_time):
    return convert_to_srt_format(float(start_time), float(end_time))

def _format_seconds(seconds):
    if seconds is None:
        return ""
    return f"{float(seconds):.3f}s"

def _leading_ack_word_count(sentence):
    match = LEADING_ACK_RE.match(str(sentence))
    if not match:
        return 0
    return len([word for word in re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", match.group(0)) if word])

def _has_bad_leading_ack_timing(df_words, start_word_idx, end_word_idx, ack_word_count):
    if ack_word_count <= 0 or start_word_idx + ack_word_count > end_word_idx:
        return False

    ack_indices = list(range(start_word_idx, start_word_idx + ack_word_count))
    ack_start = float(df_words['start'][ack_indices[0]])
    ack_end = float(df_words['end'][ack_indices[-1]])
    ack_duration = ack_end - ack_start
    max_ack_word_duration = max(_word_duration(df_words, i) for i in ack_indices)
    max_ack_internal_gap = 0
    if len(ack_indices) > 1:
        max_ack_internal_gap = max(_gap_between_words(df_words, left, right) for left, right in zip(ack_indices, ack_indices[1:]))
    gap_after_ack = _gap_between_words(df_words, ack_indices[-1], start_word_idx + ack_word_count)

    return (
        ack_duration > 3.0
        or max_ack_word_duration > 2.5
        or max_ack_internal_gap > 2.5
        or gap_after_ack > 3.0
    )

def _trim_leading_ack_from_row(df_sentences, row_idx):
    source = str(df_sentences.at[row_idx, 'Source'])
    cleaned_source = LEADING_ACK_RE.sub("", source, count=1).strip()
    if cleaned_source:
        df_sentences.at[row_idx, 'Source'] = cleaned_source

    if 'Translation' in df_sentences.columns:
        translation = str(df_sentences.at[row_idx, 'Translation'])
        cleaned_translation = LEADING_TRANSLATION_ACK_RE.sub("", translation, count=1).strip()
        if cleaned_translation:
            df_sentences.at[row_idx, 'Translation'] = cleaned_translation

    console.print(
        f"[yellow]⚠️ Trimmed leading acknowledgement from subtitle {row_idx + 1} "
        "because ASR word timestamps contain an abnormal long pause.[/yellow]"
    )

def clean_prompt_pollution(text):
    text = str(text).strip()
    if not text or text.lower() == "nan":
        return ""
    # Remove GPT meta-instructions that leaked into subtitle output
    text = re.sub(r"[（(][^)）]*(?:合并|接上|同上|见上|见下|续前|续后|merge|combine|join)[^)）]*[)）]", "", text)
    text = _clean_translation_boundary_text(text)

    text_label_match = re.search(r"(?:文本|Text)\s*[:：]\s*(.+)$", text, re.I)
    if text_label_match:
        return normalize_cjk_latin_spacing(text_label_match.group(1).strip(" .。；;"))

    term_match = re.search(r"(?:术语|Terms?|Glossary)\s*[:：]\s*[^=＝:：]+[=＝:：]\s*(.+)$", text, re.I)
    if term_match:
        text = term_match.group(1).strip(" .。；;")
        text_label_match = re.search(r"(?:文本|Text)\s*[:：]\s*(.+)$", text, re.I)
        return normalize_cjk_latin_spacing((text_label_match.group(1) if text_label_match else text).strip(" .。；;"))

    if "=" in text or "＝" in text:
        right_side = re.split(r"[=＝]", text, maxsplit=1)[-1].strip(" .。；;")
        text_label_match = re.search(r"(?:文本|Text)\s*[:：]\s*(.+)$", right_side, re.I)
        if text_label_match:
            return text_label_match.group(1).strip(" .。；;")
        return normalize_cjk_latin_spacing(right_side)

    return normalize_cjk_latin_spacing(text)

def show_difference(str1, str2):
    """Show the difference positions between two strings"""
    min_len = min(len(str1), len(str2))
    diff_positions = []

    for i in range(min_len):
        if str1[i] != str2[i]:
            diff_positions.append(i)

    if len(str1) != len(str2):
        diff_positions.extend(range(min_len, max(len(str1), len(str2))))

    print("Difference positions:")
    print(f"Expected sentence: {str1}")
    print(f"Actual match: {str2}")
    print("Position markers: " + "".join("^" if i in diff_positions else " " for i in range(max(len(str1), len(str2)))))
    print(f"Difference indices: {diff_positions}")

def _normalize_alignment_token(text):
    return remove_punctuation(str(text).lower()).strip()

def _sentence_alignment_tokens(sentence):
    return [
        token for token in (
            _normalize_alignment_token(part)
            for part in str(sentence).split()
        )
        if token
    ]

def _find_fuzzy_sentence_span(word_tokens, sentence_tokens, start_word_hint):
    if not sentence_tokens:
        return None

    best = None
    sentence_len = len(sentence_tokens)
    start_word_hint = max(0, int(start_word_hint or 0))
    max_extra_words = max(3, min(8, sentence_len // 3 + 2))
    min_window = max(1, sentence_len - 2)
    max_window = sentence_len + max_extra_words
    search_end = len(word_tokens)

    for start_idx in range(start_word_hint, search_end):
        if not word_tokens[start_idx]:
            continue
        for window_len in range(min_window, max_window + 1):
            end_idx = start_idx + window_len
            if end_idx > len(word_tokens) or end_idx > search_end:
                break
            candidate = [token for token in word_tokens[start_idx:end_idx] if token]
            if not candidate:
                continue
            score = SequenceMatcher(None, sentence_tokens, candidate).ratio()
            first_anchor = sentence_tokens[0] == candidate[0]
            last_anchor = sentence_tokens[-1] == candidate[-1]
            anchor_bonus = (0.04 if first_anchor else 0) + (0.03 if last_anchor else 0)
            adjusted_score = score + anchor_bonus
            if best is None or adjusted_score > best["score"]:
                best = {
                    "start_word_idx": start_idx,
                    "end_word_idx": end_idx - 1,
                    "score": adjusted_score,
                    "raw_score": score,
                    "candidate": candidate,
                }

    if best and (best["score"] >= 0.88 or (best["raw_score"] >= 0.84 and len(sentence_tokens) >= 8)):
        return best
    return None

def get_sentence_timestamps(df_words, df_sentences):
    time_stamp_list = []

    # Build complete string and position mapping
    full_words_str = ''
    position_to_word_idx = {}
    word_idx_to_start_pos = {}
    word_idx_to_end_pos = {}
    word_tokens = []

    for idx, word in enumerate(df_words['text']):
        clean_word = _normalize_alignment_token(word)
        start_pos = len(full_words_str)
        word_idx_to_start_pos[idx] = start_pos
        full_words_str += clean_word
        word_idx_to_end_pos[idx] = len(full_words_str)
        word_tokens.append(clean_word)
        for pos in range(start_pos, len(full_words_str)):
            position_to_word_idx[pos] = idx

    current_pos = 0
    for idx, sentence in df_sentences['Source'].items():
        clean_sentence = remove_punctuation(sentence.lower()).replace(" ", "")
        sentence_len = len(clean_sentence)

        match_found = False
        scan_start_pos = current_pos
        while current_pos <= len(full_words_str) - sentence_len:
            if full_words_str[current_pos:current_pos+sentence_len] == clean_sentence:
                start_word_idx = position_to_word_idx[current_pos]
                end_word_idx = position_to_word_idx[current_pos + sentence_len - 1]
                ack_word_count = _leading_ack_word_count(sentence)
                if _has_bad_leading_ack_timing(df_words, start_word_idx, end_word_idx, ack_word_count):
                    start_word_idx += ack_word_count
                    _trim_leading_ack_from_row(df_sentences, idx)

                speech_start = float(df_words['start'][start_word_idx])
                speech_end = _effective_word_end(df_words, start_word_idx, end_word_idx)
                time_stamp_list.append({
                    "speech_start": speech_start,
                    "speech_end": speech_end,
                    "start_word_idx": int(start_word_idx),
                    "end_word_idx": int(end_word_idx),
                    "start_word": str(df_words['text'][start_word_idx]),
                    "end_word": str(df_words['text'][end_word_idx]),
                })

                current_pos += sentence_len
                match_found = True
                break
            current_pos += 1

        if not match_found:
            start_word_hint = position_to_word_idx.get(scan_start_pos)
            if start_word_hint is None:
                start_word_hint = min(
                    range(len(word_idx_to_start_pos)),
                    key=lambda word_idx: abs(word_idx_to_start_pos[word_idx] - scan_start_pos),
                    default=0,
                )
            fuzzy_match = _find_fuzzy_sentence_span(
                word_tokens,
                _sentence_alignment_tokens(sentence),
                start_word_hint,
            )
            if fuzzy_match:
                start_word_idx = fuzzy_match["start_word_idx"]
                end_word_idx = fuzzy_match["end_word_idx"]
                speech_start = float(df_words['start'][start_word_idx])
                speech_end = _effective_word_end(df_words, start_word_idx, end_word_idx)
                time_stamp_list.append({
                    "speech_start": speech_start,
                    "speech_end": speech_end,
                    "start_word_idx": int(start_word_idx),
                    "end_word_idx": int(end_word_idx),
                    "start_word": str(df_words['text'][start_word_idx]),
                    "end_word": str(df_words['text'][end_word_idx]),
                })
                current_pos = word_idx_to_end_pos.get(end_word_idx, scan_start_pos)
                console.print(
                    f"[yellow]⚠️ Fuzzy matched subtitle source at row {idx + 1} "
                    f"(score: {fuzzy_match['raw_score']:.3f}) because exact word alignment failed.[/yellow]"
                )
                continue

            print(f"\n⚠️ Warning: No exact match found for sentence: {sentence}")
            show_difference(clean_sentence,
                          full_words_str[current_pos:current_pos+len(clean_sentence)])
            print("\nOriginal sentence:", df_sentences['Source'][idx])
            raise ValueError("❎ No match found for sentence.")

    return time_stamp_list

def _speech_duration(row):
    start_time, end_time = row["speech_timestamp"]
    return max(0.0, float(end_time) - float(start_time))

def _speech_gap(left_row, right_row):
    return float(right_row["speech_timestamp"][0]) - float(left_row["speech_timestamp"][1])

def _join_source_text(left_text, right_text):
    left = str(left_text or "").strip()
    right = str(right_text or "").strip()
    if not left:
        return right
    if not right:
        return left
    if _is_continuation_start(right) and _same_boundary_token(left, right):
        right = _remove_duplicate_leading_source_token(right)
        if not right:
            return left
    if _starts_with_lowercase_latin(right) and left.rstrip().endswith((".", "?", "!")):
        left = re.sub(r"[.!?]+$", "", left.rstrip())
    joined = re.sub(r"\s+([,.;:!?，。；：！？])", r"\1", f"{left} {right}")
    joined = _collapse_nonrepeatable_source_words(joined)
    return _apply_source_phrase_corrections(joined)

def _join_translation_text(left_text, right_text):
    left = str(left_text or "").strip()
    right = str(right_text or "").strip()
    if not left:
        return right
    if not right:
        return left
    return f"{left} {right}"

def _clean_merged_translation_for_source(source, translation):
    source_key = re.sub(r"\s+", " ", str(source or "").strip()).lower()
    translation = str(translation or "").strip()
    if source_key == "there it is.":
        translation = re.sub(r"\s+哦\s*$", "", translation).strip()
    return translation

def _row_needs_short_merge(row):
    source = str(row.get("Source", ""))
    source_words = _latin_word_count(source)
    source_chars = _visible_char_count(source)
    duration = _speech_duration(row)
    required_duration = _required_display_duration(row)
    # Single-word or 2-word fragments are always candidates for merging
    if source_words <= 2 and source_chars <= 20:
        return True
    # Very short Chinese translation (< 8 visible chars) → always merge candidate.
    # Handles cases like "丛林" (2 chars), "群岛" (2 chars) that are useless alone.
    translation = str(row.get("Translation", ""))
    trans_chars = _visible_char_count(translation)
    if trans_chars > 0 and trans_chars < 8:
        return True
    # Mid-sentence fragments: 3-7 words that start with lowercase or don't end
    # with sentence punctuation → likely split mid-sentence, should try to merge.
    if source_words >= 3 and source_chars >= 12:
        stripped = source.strip()
        starts_lowercase = bool(stripped and stripped[0].islower())
        ends_with_sentence_punct = bool(re.search(r'[.!?]$', stripped))
        # Short lowercase-starting fragments are always candidates
        if starts_lowercase and source_words <= 8:
            return True
        # Fragments without sentence-ending punctuation are always candidates
        if not ends_with_sentence_punct:
            return True
    return (
        (duration < 1.2 and (source_words >= 3 or source_chars >= 10))
        or (source_words >= 6 and duration < required_duration * 0.75)
    )

def _can_merge_rows(
    left_row,
    right_row,
    max_gap=SUBTITLE_SHORT_MERGE_MAX_GAP_SECONDS,
    max_duration=SUBTITLE_MERGE_MAX_DURATION_SECONDS,
    max_source_words=SUBTITLE_MERGE_MAX_SOURCE_WORDS,
    max_source_chars=SUBTITLE_MERGE_MAX_SOURCE_CHARS,
    max_translation_chars=SUBTITLE_MERGE_MAX_TRANSLATION_CHARS,
):
    gap = _speech_gap(left_row, right_row)
    if gap < -SUBTITLE_MAX_OVERLAP_SECONDS or gap > max_gap:
        return False

    source = _join_source_text(left_row.get("Source", ""), right_row.get("Source", ""))
    translation = _join_translation_text(left_row.get("Translation", ""), right_row.get("Translation", ""))
    combined_duration = float(right_row["speech_timestamp"][1]) - float(left_row["speech_timestamp"][0])
    return (
        _latin_word_count(source) <= max_source_words
        and _visible_char_count(source) <= max_source_chars
        and _visible_char_count(translation) <= max_translation_chars
        and combined_duration <= max_duration
    )

def _should_merge_with_previous(current):
    return _is_continuation_start(current.get("Source", ""))

def _is_short_answer_source(text):
    source = str(text or "").strip()
    return _latin_word_count(source) <= 3 and bool(SHORT_ANSWER_SOURCE_RE.match(source))

def _translation_too_long_for_short_answer(row):
    return _is_short_answer_source(row.get("Source", "")) and _visible_char_count(row.get("Translation", "")) >= 18

def _should_merge_short_answer_with_next(current, next_row):
    if not _translation_too_long_for_short_answer(current):
        return False
    next_source = str(next_row.get("Source", "") or "").strip()
    if not next_source:
        return False
    return bool(re.match(r"[A-Z]", LEADING_SOURCE_PUNCT_RE.sub("", next_source)))

def _is_sentence_boundary(prev_source, curr_source):
    """Check if prev ends with sentence punctuation and curr starts with capital,
    indicating a genuine sentence boundary that should not be merged."""
    prev = str(prev_source or "").rstrip()
    curr = str(curr_source or "").strip()
    return bool(re.search(r'[.!?]$', prev) and curr and curr[0].isupper())

def _merge_two_rows(left_row, right_row):
    merged = dict(left_row)
    merged["Source"] = _join_source_text(left_row.get("Source", ""), right_row.get("Source", ""))
    if "Translation" in merged or "Translation" in right_row:
        merged["Translation"] = _clean_merged_translation_for_source(
            merged["Source"],
            _join_translation_text(left_row.get("Translation", ""), right_row.get("Translation", "")),
        )
    merged["end_word_idx"] = right_row.get("end_word_idx", left_row.get("end_word_idx"))
    merged["end_word"] = right_row.get("end_word", left_row.get("end_word"))
    merged["speech_timestamp"] = (
        float(left_row["speech_timestamp"][0]),
        float(right_row["speech_timestamp"][1]),
    )
    merged["speech_duration"] = _speech_duration(merged)
    merged["merged_subtitle_count"] = int(left_row.get("merged_subtitle_count", 1)) + int(right_row.get("merged_subtitle_count", 1))
    return merged

def _merge_short_adjacent_subtitles(df_trans_time):
    rows = []
    for _, row in df_trans_time.iterrows():
        item = row.to_dict()
        item["merged_subtitle_count"] = int(item.get("merged_subtitle_count", 1))
        rows.append(item)

    merge_count = 0
    changed = True
    while changed:
        changed = False
        merged_rows = []
        i = 0
        while i < len(rows):
            current = rows[i]
            if (
                i + 1 < len(rows)
                and _should_merge_short_answer_with_next(current, rows[i + 1])
                and _can_merge_rows(
                    current,
                    rows[i + 1],
                    max_gap=SUBTITLE_CONTINUATION_MERGE_MAX_GAP_SECONDS,
                    max_duration=12.0,
                    max_source_words=26,
                    max_source_chars=145,
                    max_translation_chars=95,
                )
            ):
                merged_rows.append(_merge_two_rows(current, rows[i + 1]))
                merge_count += 1
                changed = True
                i += 2
                continue
            if (
                merged_rows
                and _should_merge_with_previous(current)
                and not _is_sentence_boundary(
                    merged_rows[-1].get("Source", ""), current.get("Source", "")
                )
                and _can_merge_rows(
                    merged_rows[-1],
                    current,
                    max_gap=SUBTITLE_CONTINUATION_MERGE_MAX_GAP_SECONDS,
                    max_duration=14.0,
                    max_source_words=32,
                    max_source_chars=170,
                    max_translation_chars=110,
                )
            ):
                merged_rows[-1] = _merge_two_rows(merged_rows[-1], current)
                merge_count += 1
                changed = True
                i += 1
                continue
            if _row_needs_short_merge(current):
                # When two single-word fragments are adjacent, merge them with
                # each other first.  "000." + "8" → "000. 8" as a pair, rather
                # than both being absorbed by the previous full sentence.
                if (
                    i + 1 < len(rows)
                    and _row_needs_short_merge(rows[i + 1])
                    and _can_merge_rows(current, rows[i + 1])
                ):
                    merged_rows.append(_merge_two_rows(current, rows[i + 1]))
                    merge_count += 1
                    changed = True
                    i += 2
                    continue
                if (
                    merged_rows
                    and _can_merge_rows(merged_rows[-1], current)
                    and not _is_sentence_boundary(
                        merged_rows[-1].get("Source", ""), current.get("Source", "")
                    )
                ):
                    merged_rows[-1] = _merge_two_rows(merged_rows[-1], current)
                    merge_count += 1
                    changed = True
                    i += 1
                    continue
                if (
                    i + 1 < len(rows)
                    and _can_merge_rows(current, rows[i + 1])
                    and not _is_sentence_boundary(
                        current.get("Source", ""), rows[i + 1].get("Source", "")
                    )
                ):
                    merged_rows.append(_merge_two_rows(current, rows[i + 1]))
                    merge_count += 1
                    changed = True
                    i += 2
                    continue
            merged_rows.append(current)
            i += 1
        rows = merged_rows

    if merge_count:
        console.print(
            f"[blue]ℹ️ Merged {merge_count} short adjacent subtitle segment(s) "
            "before SRT timing export.[/blue]"
        )
    return pd.DataFrame(rows).reset_index(drop=True)

def _is_likely_standalone_ack_hallucination(row, previous_row=None, next_row=None):
    source = str(row.get("Source", "") or "").strip()
    translation = str(row.get("Translation", "") or "").strip()
    if not STANDALONE_ACK_SOURCE_RE.match(source):
        return False
    if translation and not STANDALONE_ACK_TRANSLATION_RE.match(translation):
        return False
    duration = _speech_duration(row)
    if duration > 0.85:
        return False

    nearby_gaps = []
    if previous_row is not None:
        nearby_gaps.append(_speech_gap(previous_row, row))
    if next_row is not None:
        nearby_gaps.append(_speech_gap(row, next_row))
    return bool(nearby_gaps and min(abs(gap) for gap in nearby_gaps) <= 0.5)

def _drop_likely_standalone_ack_hallucinations(df_trans_time):
    if df_trans_time.empty or "Source" not in df_trans_time.columns:
        return df_trans_time

    rows = [row.to_dict() for _, row in df_trans_time.iterrows()]
    kept_rows = []
    dropped_count = 0
    for index, row in enumerate(rows):
        previous_row = rows[index - 1] if index > 0 else None
        next_row = rows[index + 1] if index + 1 < len(rows) else None
        if _is_likely_standalone_ack_hallucination(row, previous_row, next_row):
            dropped_count += 1
            continue
        kept_rows.append(row)

    if dropped_count:
        console.print(f"[blue]ℹ️ Removed {dropped_count} likely standalone acknowledgement hallucination(s) before SRT export.[/blue]")
    return pd.DataFrame(kept_rows).reset_index(drop=True)

def _apply_word_anchored_display_timing(df_trans_time):
    display_timestamps = []
    report_items = []

    for i, row in df_trans_time.iterrows():
        speech_start, speech_end = row["speech_timestamp"]
        speech_start = float(speech_start)
        speech_end = float(speech_end)
        next_start = None
        if i + 1 < len(df_trans_time):
            next_start = float(df_trans_time.at[i + 1, "speech_timestamp"][0])

        required_duration = _required_display_duration(row)
        speech_duration = max(0.0, speech_end - speech_start)
        display_end = speech_end
        status = "ok"
        reason = "word-level speech timing preserved"

        if next_start is not None and speech_end - next_start > SUBTITLE_MAX_OVERLAP_SECONDS:
            clipped_end = max(speech_start + SUBTITLE_MIN_DURATION_SECONDS, next_start - 0.02)
            if clipped_end < speech_end:
                display_end = clipped_end
                status = "clipped_overlap"
                reason = "word timestamps overlap the next subtitle"
        else:
            safe_end = speech_end + SUBTITLE_MAX_SAFE_EXTENSION_SECONDS
            if next_start is not None:
                safe_end = min(safe_end, next_start - SUBTITLE_NEXT_START_GUARD_SECONDS)

            target_end = max(
                speech_end + SUBTITLE_DISPLAY_TAIL_SECONDS,
                speech_start + required_duration,
            )
            target_end = min(target_end, safe_end)
            long_silence_end = None
            if speech_duration + 0.02 < required_duration:
                long_silence_end = _long_silence_display_end(row, speech_end, next_start)
            if long_silence_end is not None and long_silence_end > target_end:
                target_end = long_silence_end
            if target_end > speech_end:
                display_end = target_end
                status = "extended"
                reason = "display time extended inside silence after the last word"
                if long_silence_end is not None and abs(target_end - long_silence_end) < 0.001:
                    status = "extended_to_silence"
                    reason = "display time extended through a long silence before the next subtitle"

        display_duration = max(0.0, display_end - speech_start)
        if display_duration + 0.02 < required_duration:
            if next_start is not None and next_start - speech_end <= SUBTITLE_NEXT_START_GUARD_SECONDS:
                status = "still_short_no_room"
                reason = "next subtitle starts immediately; cannot extend without covering speech"
            elif status == "extended":
                status = "extended_but_still_short"
                reason = "extended safely, but still shorter than readability target"
            else:
                status = "still_short"
                reason = "shorter than readability target"

        display_timestamps.append((speech_start, display_end))
        report_items.append({
            "subtitle_index": int(i) + 1,
            "status": status,
            "reason": reason,
            "merged_subtitle_count": int(row.get("merged_subtitle_count", 1)),
            "source": str(row.get("Source", "")),
            "translation": str(row.get("Translation", "")),
            "start_word_index": int(row.get("start_word_idx", -1)) + 1,
            "end_word_index": int(row.get("end_word_idx", -1)) + 1,
            "start_word": str(row.get("start_word", "")),
            "end_word": str(row.get("end_word", "")),
            "speech_timestamp": _format_timestamp_range(speech_start, speech_end),
            "display_timestamp": _format_timestamp_range(speech_start, display_end),
            "speech_duration": round(speech_duration, 3),
            "display_duration": round(display_duration, 3),
            "required_display_duration": round(required_duration, 3),
            "available_gap_to_next": round(next_start - speech_end, 3) if next_start is not None else None,
        })

    df_trans_time["display_timestamp"] = display_timestamps
    df_trans_time["duration"] = df_trans_time["display_timestamp"].apply(lambda x: x[1] - x[0])
    return report_items

def _write_subtitle_timing_report(report_items):
    if not report_items:
        return

    os.makedirs(os.path.dirname(SUBTITLE_TIMING_REPORT_JSON), exist_ok=True)
    with open(SUBTITLE_TIMING_REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report_items, f, ensure_ascii=False, indent=2)

    status_counts = {}
    for item in report_items:
        status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1

    lines = [
        "# Subtitle Timing Quality Report",
        "",
        "This report keeps Whisper word-level speech anchors separate from subtitle display timing.",
        "",
        "## Summary",
        "",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"- {status}: {count}")

    review_statuses = {
        "clipped_overlap",
        "extended_but_still_short",
        "still_short",
        "still_short_no_room",
    }
    review_items = [item for item in report_items if item["status"] in review_statuses]
    if review_items:
        lines.extend(["", "## Items To Review", ""])
        for item in review_items:
            lines.extend([
                f"### {item['subtitle_index']}. {item['status']}",
                f"- Speech: {item['speech_timestamp']}",
                f"- Display: {item['display_timestamp']}",
                f"- Merged source segments: {item['merged_subtitle_count']}",
                f"- Word anchor: #{item['start_word_index']} `{item['start_word']}` -> #{item['end_word_index']} `{item['end_word']}`",
                f"- Duration: speech {_format_seconds(item['speech_duration'])}, display {_format_seconds(item['display_duration'])}, required {_format_seconds(item['required_display_duration'])}",
                f"- Gap to next: {_format_seconds(item['available_gap_to_next']) if item['available_gap_to_next'] is not None else 'N/A'}",
                f"- Reason: {item['reason']}",
                f"- Source: {item['source']}",
                f"- Translation: {item['translation']}",
                "",
            ])

    with open(SUBTITLE_TIMING_REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

def _subtitle_split_style_for_video(target_width, target_height):
    if target_width and target_height and _is_portrait_video(target_width, target_height):
        _, trans_size = _portrait_font_sizes(target_width)
        margin_h = _portrait_safe_side_margin(target_width)
        return trans_size, margin_h
    width = int(target_width or 1920)
    return TRANS_FONT_SIZE if "TRANS_FONT_SIZE" in globals() else 48, max(40, int(round(width * 0.05)))

def _split_source_by_punctuation(source_text):
    text = re.sub(r"\s+", " ", str(source_text or "").strip())
    if not text:
        return []

    pieces = []
    last = 0
    for match in re.finditer(r"[.,;:。；：!?！？]+", text):
        punct = match.group(0)
        if "..." in punct or "…" in punct:
            continue
        leading_text = text[last:match.start()].strip()
        if punct in {",", "，"} and re.fullmatch(
            r"(?i)(well|yeah|yes|no|right|okay|ok|so|but|and|i mean|you know)",
            leading_text.strip(" ,"),
        ):
            continue
        end = match.end()
        piece = text[last:end].strip()
        if piece:
            pieces.append(piece)
        last = end
    tail = text[last:].strip()
    if tail:
        pieces.append(tail)
    return pieces

def _restore_missing_source_question_boundaries(source_text):
    text = re.sub(r"\s+", " ", str(source_text or "").strip())
    if not text:
        return ""

    question_patterns = [
        r"\b(how\s+did\s+you\s+do\s+that)\s+(?=(?:it'?s|that'?s|this|there|i|you|he|she|we|they)\b)",
        r"\b(what\s+(?:are|were|is|was|do|does|did|can|could|would|should|will)\s+[^.!?]{2,80}?)\s+(?=(?:it'?s|that'?s|this|there|i|you|he|she|we|they)\b)",
        r"\b(why\s+(?:are|were|is|was|do|does|did|can|could|would|should|will)\s+[^.!?]{2,80}?)\s+(?=(?:it'?s|that'?s|this|there|i|you|he|she|we|they)\b)",
    ]
    for pattern in question_patterns:
        text = re.sub(pattern, lambda match: match.group(1).rstrip(" ?") + "? ", text, flags=re.I)
    return text

def _source_sentence_parts_for_display(source_text):
    source_text = _restore_missing_source_question_boundaries(source_text)
    ellipsis_question_answer = re.match(r"^(.+?\.\.\.)\s+(But\b.+?\?)\s+(Yeah,\s+but\b.+)$", source_text, re.I)
    if ellipsis_question_answer:
        return [
            ellipsis_question_answer.group(1).strip(),
            ellipsis_question_answer.group(2).strip(),
            ellipsis_question_answer.group(3).strip(),
        ]
    parts = []
    for part in _split_source_by_sentence_punctuation(source_text):
        parts.extend(_split_repeated_parallel_markers(part, ("how much", "what")))
    if len(parts) <= 1:
        return []
    return parts

def _source_sentence_parts_for_timeline(source_text):
    parts = _source_sentence_parts_for_display(source_text)
    if len(parts) <= 1:
        return []
    if len(parts) == 2:
        first = parts[0].strip()
        second = parts[1].strip()
        if re.search(r"\?\s*$", first) and not re.match(r"(?i)i\s+mean\b", second):
            return parts
        if re.search(r"[.!?]\s*$", first) and re.match(r"(?i)i\s+heard\b", second):
            return parts
        return []
    if (
        len(parts) == 3
        and re.search(r"\.\.\.\s*$", parts[0].strip())
        and re.search(r"\?\s*$", parts[1].strip())
        and re.match(r"(?i)yeah,\s+but\b", parts[2].strip())
    ):
        return parts
    return []

def _source_clause_parts_for_display(source_text):
    text = re.sub(r"\s+", " ", str(source_text or "").strip())
    if not text:
        return []

    match = re.match(r"^(.+?,)\s+(and\b.+?)\s+(because\b.+)$", text, re.I)
    if match:
        parts = [match.group(1).strip(), match.group(2).strip(), match.group(3).strip()]
        if any(_latin_word_count(part) < 3 for part in parts):
            return []
        return parts

    if _has_repeated_parallel_markers(text):
        return []

    semantic_patterns = [
        r"^(.+?)\s+(and\s+among\s+them\b.+)$",
        r"^(.+?)\s+(and\s+now\b.+)$",
        r"^(.+?)\s+(and\s+automatically\b.+)$",
        r"^(.+?)\s+(and\s+over\s+the\s+summer\b.+)$",
        r"^(.+?)\s+(then\s+in\s+\d{4}\b.+)$",
        r"^(.+?)\s+(because\b.+)$",
        r"^(.+?)\s+(since\b.+)$",
        r"^(.+?)\s+(that\s+monitors\b.+)$",
        r"^(.+?)\s+(but\b.+)$",
    ]
    for pattern in semantic_patterns:
        match = re.match(pattern, text, re.I)
        if not match:
            continue
        parts = [match.group(1).strip(" ,"), match.group(2).strip()]
        if re.fullmatch(r"(?i)(well|yeah|yes|no|right|okay|ok|so|but|and|i\s+mean|you\s+know|well,\s+i\s+think)", parts[0]):
            continue
        if all(_latin_word_count(part) >= 3 for part in parts):
            return parts

    return []

def _split_source_by_sentence_punctuation(source_text):
    text = re.sub(r"\s+", " ", str(source_text or "").strip())
    if not text:
        return []

    pieces = []
    last = 0
    for match in re.finditer(r"[.!?！？]+|,\s+(?=(?:how|what|why|where|when|who)\b)", text, re.I):
        if "..." in match.group(0) or "…" in match.group(0):
            continue
        if match.group(0).lstrip().startswith(","):
            leading_text = text[last:match.start()].strip()
            if _latin_word_count(leading_text) > 5:
                continue
        end = match.end()
        piece = text[last:end].strip()
        if piece:
            pieces.append(piece)
        last = end
    tail = text[last:].strip()
    if tail:
        pieces.append(tail)
    return pieces

def _is_leading_continuation_fragment(fragment):
    text = re.sub(r"\s+", " ", str(fragment or "").strip())
    if not text:
        return False
    if re.fullmatch(r"(?i)(actually|really|though|anyway|too|also|then)[.!?]?", text):
        return True
    return text[:1].islower()

def _split_translation_leading_actually(translation):
    text = re.sub(r"\s+", " ", str(translation or "").strip())
    match = re.match(r"^(其实|实际上)[。.!?？,，、\s]*(.+)$", text)
    if not match:
        return None
    return match.group(1), match.group(2).strip()

def _prepend_chinese_actually_translation(translation, actually_translation):
    text = re.sub(r"\s+", " ", str(translation or "").strip())
    marker = str(actually_translation or "").strip()
    if not text or not marker:
        return text
    if re.match(r"^(?:我\s*)?不(?:知道|确定)\b", text):
        text = re.sub(r"^(?:我\s*)?不(?:知道|确定)[,，、\s]*", "", text).strip()
        return f"我也说不准 {marker}{text}".strip()
    return f"{marker}{text}".strip()

def _split_repeated_parallel_markers(text, markers):
    text = re.sub(r"\s+", " ", str(text or "").strip())
    if not text:
        return []

    best_marker = None
    best_matches = []
    for marker in markers:
        pattern = re.compile(rf"\b{re.escape(marker)}\b", re.I)
        matches = list(pattern.finditer(text))
        if len(matches) >= 2 and (not best_matches or matches[1].start() < best_matches[1].start()):
            best_marker = marker
            best_matches = matches

    if not best_marker:
        return [text]

    boundaries = [0] + [match.start() for match in best_matches[1:]] + [len(text)]
    parts = [
        text[boundaries[index]:boundaries[index + 1]].strip(" ,，")
        for index in range(len(boundaries) - 1)
    ]
    return [part for part in parts if part]

def _has_repeated_parallel_markers(text, markers=("how much", "what")):
    text = re.sub(r"\s+", " ", str(text or "").strip())
    return any(
        len(list(re.finditer(rf"\b{re.escape(marker)}\b", text, re.I))) >= 2
        for marker in markers
    )

def _split_translation_by_sentence_boundaries(translation):
    text = re.sub(r"\s+", " ", str(translation or "").strip())
    if not text:
        return []

    parts = []
    for space_part in _split_on_cjk_semantic_spaces(text) or [text]:
        start = 0
        for match in re.finditer(r"[，,。.!？?！；;、]+", space_part):
            end = match.end()
            part = space_part[start:end].strip(" ，,。；;：:、")
            if part:
                parts.append(part)
            start = end
        tail = space_part[start:].strip(" ，,。；;：:、")
        if tail:
            parts.append(tail)
    split_parts = []
    for part in parts:
        split_parts.extend(
            _split_repeated_parallel_markers(
                part,
                ("o que", "quanto", "how much", "what"),
            )
        )
    return [part for part in split_parts if part]

def _translation_parts_matching_source(translation, part_count, source_parts=None):
    if part_count <= 1:
        return []
    parts = _split_translation_by_sentence_boundaries(translation)
    if len(parts) < part_count:
        expanded_parts = []
        for part in parts:
            split_parts = _split_translation_clause_markers(part)
            expanded_parts.extend(split_parts or [part])
        parts = expanded_parts
    if len(parts) < part_count:
        return []
    source_parts = [str(part or "").strip() for part in (source_parts or [])]
    if (
        len(parts) > part_count
        and part_count == 2
        and len(source_parts) == 2
        and re.search(r"\?\s*$", source_parts[0])
        and re.search(r"[？?]\s*$", parts[0])
    ):
        return [parts[0], " ".join(parts[1:]).strip()]
    if (
        len(parts) > part_count
        and part_count == 3
        and len(source_parts) == 3
        and re.search(r"doesn'?t\s+rhyme\s+with\s+anything,?\s*$", source_parts[0], re.I)
        and re.match(r"(?i)and\s+that\b", source_parts[1])
        and re.match(r"(?i)because\b", source_parts[2])
        and re.search(r"任何词|什么词|任何", parts[1])
        and re.match(r"^(这点|这一点|这事|这就)", parts[2])
    ):
        return [
            f"{parts[0]} {parts[1]}".strip(),
            parts[2],
            " ".join(parts[3:]).strip(),
        ]
    if (
        len(parts) > part_count
        and part_count == 2
        and len(source_parts) == 2
        and re.match(r"(?i)but\b", source_parts[1])
    ):
        for index, part in enumerate(parts[1:], 1):
            if re.match(r"^(但|但是|不过|可是|却)", part):
                return [
                    " ".join(parts[:index]).strip(),
                    " ".join(parts[index:]).strip(),
                ]
    semantic_space_parts = _split_on_cjk_semantic_spaces(translation)
    if len(semantic_space_parts) == part_count:
        return semantic_space_parts
    if len(parts) > part_count:
        parts = _merge_source_parts_to_count(parts, part_count)
    return parts if len(parts) == part_count else []

def _split_translation_clause_markers(translation):
    text = re.sub(r"\s+", " ", str(translation or "").strip())
    if not text:
        return []
    parts = [text]
    for marker in ("porque", "because"):
        expanded = []
        pattern = re.compile(rf"\s+(?={re.escape(marker)}\b)", re.I)
        for part in parts:
            split_parts = [item.strip(" ，,。；;：:、") for item in pattern.split(part, maxsplit=1)]
            expanded.extend([item for item in split_parts if item])
        parts = expanded
    return parts

def _merge_source_parts_to_count(parts, part_count):
    parts = [part.strip() for part in parts if part and part.strip()]
    if part_count <= 1 or len(parts) <= part_count:
        return parts

    while len(parts) > part_count:
        best_index = min(
            range(len(parts) - 1),
            key=lambda index: _text_weight(parts[index]) + _text_weight(parts[index + 1]),
        )
        parts[best_index] = f"{parts[best_index]} {parts[best_index + 1]}".strip()
        del parts[best_index + 1]
    return parts

def _source_parts_by_semantics(source_text, part_count):
    punct_parts = _split_source_by_punctuation(source_text)
    if len(punct_parts) >= part_count:
        parts = _merge_source_parts_to_count(punct_parts, part_count)
        if len(parts) == part_count:
            return parts
    return []

def _source_parts_by_word_count(source_text, part_count):
    semantic_parts = _source_parts_by_semantics(source_text, part_count)
    if semantic_parts:
        return semantic_parts

    words = re.findall(r"\S+", str(source_text or "").strip())
    if part_count <= 1 or len(words) < part_count:
        return [str(source_text or "").strip()] * max(1, part_count)

    protected_boundaries = set()
    for index in range(len(words) - 1):
        left = re.sub(r"^[^\w]+|[^\w]+$", "", words[index])
        right = re.sub(r"^[^\w]+|[^\w]+$", "", words[index + 1])
        if left[:1].isupper() and right[:1].isupper():
            protected_boundaries.add(index + 1)

    def safe_boundary(raw_index):
        raw_index = max(1, min(len(words) - 1, int(raw_index)))
        if raw_index not in protected_boundaries:
            return raw_index

        for offset in range(1, len(words)):
            left_candidate = raw_index - offset
            if left_candidate > 0 and left_candidate not in protected_boundaries:
                return left_candidate
            right_candidate = raw_index + offset
            if right_candidate < len(words) and right_candidate not in protected_boundaries:
                return right_candidate
        return raw_index

    boundaries = [0]
    for index in range(1, part_count):
        boundary = safe_boundary(round(index * len(words) / part_count))
        if boundary <= boundaries[-1]:
            boundary = min(len(words) - 1, boundaries[-1] + 1)
        boundaries.append(boundary)
    boundaries.append(len(words))

    parts = []
    for index in range(part_count):
        start = boundaries[index]
        end = boundaries[index + 1]
        parts.append(" ".join(words[start:end]).strip())
    return [part or str(source_text or "").strip() for part in parts]

def _text_weight(text):
    units = 0.0
    for char in str(text or ""):
        if char.isspace():
            continue
        units += 1.0 if ord(char) > 127 else 0.55
    return max(1.0, units)

def _split_time_span(start, end, weights):
    start = float(start)
    end = float(end)
    duration = max(0.0, end - start)
    total_weight = sum(weights) or len(weights) or 1
    boundaries = [start]
    elapsed = 0.0
    for weight in weights[:-1]:
        elapsed += duration * (weight / total_weight)
        boundaries.append(start + elapsed)
    boundaries.append(end)
    return [(boundaries[index], boundaries[index + 1]) for index in range(len(weights))]

def _word_anchor_spans_for_parts(row, source_parts, display_timestamp, speech_timestamp, df_words):
    if df_words is None:
        return None
    try:
        start_idx = int(row.get("start_word_idx"))
        end_idx = int(row.get("end_word_idx"))
    except (TypeError, ValueError):
        return None
    if start_idx < 0 or end_idx < start_idx or end_idx >= len(df_words):
        return None

    part_word_counts = [_latin_word_count(part) for part in source_parts]
    if not part_word_counts or sum(part_word_counts) != end_idx - start_idx + 1:
        return None

    word_ranges = []
    current_idx = start_idx
    for count in part_word_counts:
        part_start = current_idx
        part_end = current_idx + count - 1
        word_ranges.append((part_start, part_end))
        current_idx = part_end + 1

    speech_spans = []
    display_spans = []
    for index, (part_start, part_end) in enumerate(word_ranges):
        speech_start = float(df_words["start"].iloc[part_start])
        speech_end = _effective_word_end(df_words, part_start, part_end)
        display_start = float(display_timestamp[0]) if index == 0 else speech_start
        if index + 1 < len(word_ranges):
            next_start = float(df_words["start"].iloc[word_ranges[index + 1][0]])
            display_end = next_start
        else:
            display_end = float(display_timestamp[1])
        speech_spans.append((speech_start, speech_end))
        display_spans.append((display_start, display_end))
    return word_ranges, speech_spans, display_spans

def _contains_cjk(text):
    return bool(re.search(r"[\u3400-\u9fff]", str(text or "")))

CJK_DISCOURSE_MARKERS = {
    "其实", "事实上", "说实话", "老实说", "坦白说",
    "不过", "但是", "可是", "所以", "然后", "而且",
    "我意思是", "我的意思是", "也就是说", "换句话说",
}

SOURCE_DISCOURSE_MARKERS = {
    "well", "so", "but", "and", "or", "actually", "basically",
    "honestly", "look", "listen", "okay", "ok",
}

def _merge_translation_parts_for_discourse(raw_parts):
    if len(raw_parts) < 2:
        return raw_parts
    first = raw_parts[0].strip()
    if first not in CJK_DISCOURSE_MARKERS:
        return raw_parts
    return [first, "".join(raw_parts[1:]).strip()]

def _is_cjk_char(char):
    return bool(char and "\u3400" <= char <= "\u9fff")

def _has_explicit_cjk_semantic_space(text):
    return bool(re.search(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", str(text or "")))

def _split_on_cjk_semantic_spaces(text):
    text = str(text or "").strip()
    if not text:
        return []

    parts = []
    start = 0
    for match in re.finditer(r"\s+", text):
        left_index = match.start() - 1
        right_index = match.end()
        if left_index < 0 or right_index >= len(text):
            continue
        if _is_cjk_char(text[left_index]) and _is_cjk_char(text[right_index]):
            part = text[start:match.start()].strip()
            if part:
                parts.append(part)
            start = match.end()
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts

def _semantic_translation_parts(translation, target_width, font_size, margin_h):
    text = re.sub(r"\s+", " ", str(translation or "").strip())
    if not text:
        return []

    raw_parts = []
    for punct_part in re.split(r"[，,；;。、]+", text):
        punct_part = punct_part.strip(" ，,。；;：:、")
        if not punct_part:
            continue
        raw_parts.extend(
            part.strip(" ，,。；;：:、")
            for part in _split_on_cjk_semantic_spaces(punct_part)
            if part.strip(" ，,。；;：:、")
        )
    if len(raw_parts) <= 1:
        return []
    raw_parts = _merge_translation_parts_for_discourse(raw_parts)

    # Keep timed subtitle splits semantic. Visual wrapping inside each semantic
    # part is handled later when generating ASS, so a complete phrase is not
    # split into short orphan timed entries just because the portrait font is
    # large.
    return raw_parts if len(raw_parts) >= 2 else []

def _should_split_long_display_subtitle(translation, display_timestamp, target_width, target_height):
    if not target_width or not target_height:
        return []
    start, end = display_timestamp
    duration = float(end) - float(start)
    if duration < 2.4:
        return []

    trans_size, margin_h = _subtitle_split_style_for_video(target_width, target_height)
    if _contains_cjk(translation):
        semantic_parts = _semantic_translation_parts(translation, target_width, trans_size, margin_h)
        if not semantic_parts:
            return []

        # Split long burn-in subtitles by semantic clauses even when CPS is
        # acceptable. A 9-13s subtitle with multiple clauses is visually heavy
        # on landscape video, even if the average reading speed looks fine.
        total_cjk_chars = _visible_char_count(translation)
        cps = total_cjk_chars / duration if duration > 0 else 999
        is_portrait = _is_portrait_video(target_width, target_height)
        explicit_semantic_space = _has_explicit_cjk_semantic_space(translation)
        long_semantic_subtitle = (
            duration >= 6.0
            and total_cjk_chars >= 18
            and (
                explicit_semantic_space
                or len(semantic_parts) >= 3
                or len(semantic_parts) == 2
            )
        )
        if cps <= SUBTITLE_MAX_TRANSLATION_CPS and not long_semantic_subtitle and (
            not is_portrait or not explicit_semantic_space
        ):
            return []

        if long_semantic_subtitle and len(semantic_parts) >= 2:
            return semantic_parts

        if len(semantic_parts) >= 3 or (
            len(semantic_parts) == 2 and semantic_parts[0] in CJK_DISCOURSE_MARKERS
        ):
            return semantic_parts

    return []

def _split_long_display_subtitles(df_trans_time, target_width=None, target_height=None, df_words=None):
    if df_trans_time.empty or not target_width or not target_height:
        return df_trans_time

    rows = []
    split_count = 0
    for _, row in df_trans_time.iterrows():
        display_timestamp = row.get("display_timestamp")
        if not isinstance(display_timestamp, tuple) or len(display_timestamp) != 2:
            rows.append(row.to_dict())
            continue

        trans_parts = _should_split_long_display_subtitle(
            row.get("Translation", ""),
            display_timestamp,
            target_width,
            target_height,
        )
        source_parts = []
        source_sentence_parts = _source_sentence_parts_for_timeline(row.get("Source", ""))
        if source_sentence_parts:
            matched_trans_parts = _translation_parts_matching_source(
                row.get("Translation", ""),
                len(source_sentence_parts),
                source_sentence_parts,
            )
            if matched_trans_parts:
                source_parts = source_sentence_parts
                trans_parts = matched_trans_parts
        source_clause_parts = _source_clause_parts_for_display(row.get("Source", ""))
        if source_clause_parts and not source_parts:
            matched_trans_parts = _translation_parts_matching_source(
                row.get("Translation", ""),
                len(source_clause_parts),
                source_clause_parts,
            )
            if matched_trans_parts:
                source_parts = source_clause_parts
                trans_parts = matched_trans_parts
        duration = float(display_timestamp[1]) - float(display_timestamp[0])
        allow_source_split = _is_portrait_video(
            target_width, target_height
        ) or _has_repeated_parallel_markers(row.get("Source", ""))
        if not trans_parts and duration >= 2.4 and allow_source_split:
            source_parts = _source_sentence_parts_for_display(row.get("Source", ""))
            trans_parts = _translation_parts_matching_source(
                row.get("Translation", ""),
                len(source_parts),
                source_parts,
            )
            if not trans_parts:
                source_parts = []
        if not trans_parts and duration >= 5.0:
            source_parts = _source_clause_parts_for_display(row.get("Source", ""))
            trans_parts = _translation_parts_matching_source(
                row.get("Translation", ""),
                len(source_parts),
                source_parts,
            )
            if not trans_parts:
                source_parts = []
        if not trans_parts and duration >= 2.4:
            source_parts = _source_sentence_parts_for_timeline(row.get("Source", ""))
            trans_parts = _translation_parts_matching_source(
                row.get("Translation", ""),
                len(source_parts),
                source_parts,
            )
            if not trans_parts:
                source_parts = []
        if not trans_parts:
            rows.append(row.to_dict())
            continue

        if not source_parts:
            source_parts = _source_parts_by_semantics(row.get("Source", ""), len(trans_parts))
        if not source_parts:
            if allow_source_split:
                source_parts = _source_parts_by_word_count(row.get("Source", ""), len(trans_parts))
            else:
                rows.append(row.to_dict())
                continue
        weights = [
            max(_text_weight(source_parts[index]), _text_weight(trans_parts[index]))
            for index in range(len(trans_parts))
        ]
        speech_timestamp = row.get("speech_timestamp", display_timestamp)
        anchored_spans = _word_anchor_spans_for_parts(
            row, source_parts, display_timestamp, speech_timestamp, df_words
        )
        if anchored_spans:
            word_ranges, speech_spans, display_spans = anchored_spans
        else:
            word_ranges = []
            display_spans = _split_time_span(display_timestamp[0], display_timestamp[1], weights)
            speech_spans = (
                _split_time_span(speech_timestamp[0], speech_timestamp[1], weights)
                if isinstance(speech_timestamp, tuple) and len(speech_timestamp) == 2
                else display_spans
            )

        if len(trans_parts) >= 4 and not _has_repeated_parallel_markers(row.get("Source", "")):
            unreadable_split = False
            for trans_part, span in zip(trans_parts, display_spans):
                span_duration = max(float(span[1]) - float(span[0]), 0.001)
                visible_chars = _visible_char_count(trans_part)
                if span_duration < 1.5 and visible_chars / span_duration > SUBTITLE_MAX_TRANSLATION_CPS:
                    unreadable_split = True
                    break
            if unreadable_split:
                rows.append(row.to_dict())
                continue

        for part_index, trans_part in enumerate(trans_parts):
            new_row = row.to_dict()
            new_row["Source"] = source_parts[part_index]
            new_row["Translation"] = trans_part
            new_row["display_timestamp"] = display_spans[part_index]
            new_row["speech_timestamp"] = speech_spans[part_index]
            if word_ranges:
                part_start, part_end = word_ranges[part_index]
                new_row["start_word_idx"] = part_start
                new_row["end_word_idx"] = part_end
                new_row["start_word"] = str(df_words["text"].iloc[part_start])
                new_row["end_word"] = str(df_words["text"].iloc[part_end])
            rows.append(new_row)
        split_count += 1

    if split_count:
        console.print(f"[blue]ℹ️ Split {split_count} long subtitle(s) into multiple timed SRT entries before export.[/blue]")
    return pd.DataFrame(rows).reset_index(drop=True)

def _repair_leading_sentence_continuations(df_trans_time, df_words=None):
    if df_trans_time.empty or "Source" not in df_trans_time.columns:
        return df_trans_time

    rows = [row.to_dict() for _, row in df_trans_time.iterrows()]
    repaired_count = 0
    index = 0
    while index < len(rows) - 1:
        current = rows[index]
        next_row = rows[index + 1]
        current_source = str(current.get("Source", "") or "").strip()
        next_source = str(next_row.get("Source", "") or "").strip()
        if not current_source or not next_source:
            index += 1
            continue

        next_parts = _split_source_by_sentence_punctuation(next_source)
        if len(next_parts) < 2 or not _is_leading_continuation_fragment(next_parts[0]):
            index += 1
            continue
        if re.search(r"[.!?]\s*$", current_source) and not re.fullmatch(
            r"(?i)actually[.!?]?",
            next_parts[0].strip(),
        ):
            index += 1
            continue

        moved_source = next_parts[0]
        remaining_source = " ".join(next_parts[1:]).strip()
        trans_parts = _split_translation_by_sentence_boundaries(next_row.get("Translation", ""))
        is_actually_fragment = re.fullmatch(r"(?i)actually[.!?]?", moved_source.strip())
        if len(trans_parts) < 2 and is_actually_fragment:
            split_translation = _split_translation_leading_actually(next_row.get("Translation", ""))
            if split_translation:
                trans_parts = list(split_translation)
        if len(trans_parts) < 2:
            index += 1
            continue
        moved_translation = trans_parts[0]
        remaining_translation = " ".join(trans_parts[1:]).strip()
        current_translation = current.get("Translation", "")
        if is_actually_fragment and re.fullmatch(
            r"(其实|实际上)[。.!?？]*",
            moved_translation.strip(),
        ):
            current_translation = _prepend_chinese_actually_translation(current_translation, moved_translation)
            moved_translation = ""

        try:
            next_start_idx = int(next_row.get("start_word_idx"))
            moved_word_count = _latin_word_count(moved_source)
            moved_end_idx = next_start_idx + moved_word_count - 1
            remaining_start_idx = moved_end_idx + 1
            next_end_idx = int(next_row.get("end_word_idx"))
        except (TypeError, ValueError):
            next_start_idx = moved_end_idx = remaining_start_idx = next_end_idx = None

        current["Source"] = _join_source_text(current_source, moved_source)
        current["Translation"] = _join_translation_text(current_translation, moved_translation)
        next_row["Source"] = remaining_source
        next_row["Translation"] = remaining_translation

        if df_words is not None and moved_end_idx is not None and remaining_start_idx <= next_end_idx:
            current["end_word_idx"] = moved_end_idx
            current["end_word"] = str(df_words["text"].iloc[moved_end_idx])
            next_row["start_word_idx"] = remaining_start_idx
            next_row["start_word"] = str(df_words["text"].iloc[remaining_start_idx])
            current["speech_timestamp"] = (
                float(current["speech_timestamp"][0]),
                _effective_word_end(df_words, int(current.get("start_word_idx", moved_end_idx)), moved_end_idx),
            )
            next_row["speech_timestamp"] = (
                float(df_words["start"].iloc[remaining_start_idx]),
                float(next_row["speech_timestamp"][1]),
            )
            boundary = float(df_words["start"].iloc[remaining_start_idx])
            current["display_timestamp"] = (float(current["display_timestamp"][0]), boundary)
            next_row["display_timestamp"] = (boundary, float(next_row["display_timestamp"][1]))
            current["speech_duration"] = current["speech_timestamp"][1] - current["speech_timestamp"][0]
            next_row["speech_duration"] = next_row["speech_timestamp"][1] - next_row["speech_timestamp"][0]

        repaired_count += 1
        index += 2

    if repaired_count:
        console.print(f"[blue]ℹ️ Repaired {repaired_count} leading sentence continuation(s) before SRT export.[/blue]")
    return pd.DataFrame(rows).reset_index(drop=True)

def _repair_adjacent_source_phrase_splits(df_trans_time):
    if df_trans_time.empty or "Source" not in df_trans_time.columns:
        return df_trans_time

    df_trans_time = df_trans_time.copy()
    index = 0
    repaired_count = 0
    while index < len(df_trans_time) - 1:
        repaired = False
        for window_size in (3, 2):
            if index + window_size > len(df_trans_time):
                continue
            source_values = [
                str(df_trans_time.iloc[index + offset].get("Source", "")).strip()
                for offset in range(window_size)
            ]
            if any(
                pd.notna(df_trans_time.iloc[index + offset].get("start_word_idx"))
                or pd.notna(df_trans_time.iloc[index + offset].get("end_word_idx"))
                for offset in range(window_size)
            ):
                index += window_size
                repaired = True
                break
            if any(not value for value in source_values):
                continue
            if re.search(r"[.!?]\s*$", source_values[0]):
                continue
            if not re.search(r"[.,;:!?]\s+\S", source_values[0]):
                continue
            combined_source = " ".join(source_values)
            semantic_parts = _split_source_by_punctuation(combined_source)
            if len(semantic_parts) != window_size:
                continue
            first_part_key = remove_punctuation(semantic_parts[0]).strip().lower()
            if first_part_key in SOURCE_DISCOURSE_MARKERS:
                continue
            if semantic_parts == source_values:
                continue
            if any(not LATIN_WORD_RE.search(part) for part in semantic_parts):
                continue
            for offset, part in enumerate(semantic_parts):
                df_trans_time.at[df_trans_time.index[index + offset], "Source"] = part
            repaired_count += 1
            index += window_size
            repaired = True
            break
        if not repaired:
            index += 1

    if repaired_count:
        console.print(f"[blue]ℹ️ Repaired {repaired_count} adjacent source phrase split(s) before SRT export.[/blue]")
    return df_trans_time

LEADING_PROGRAM_TITLE_QUESTION_RE = re.compile(
    r"^(60\s+Minutes\s+Rewind)\s+(.+\?)$",
    re.I,
)


def _split_leading_program_title_question(df_trans_time, df_words=None):
    if df_trans_time.empty or df_words is None or df_words.empty:
        return df_trans_time
    if "Source" not in df_trans_time.columns or "Translation" not in df_trans_time.columns:
        return df_trans_time

    rows = [row.to_dict() for _, row in df_trans_time.iterrows()]
    if not rows:
        return df_trans_time

    first = rows[0]
    source_match = LEADING_PROGRAM_TITLE_QUESTION_RE.match(str(first.get("Source", "")).strip())
    if not source_match:
        return df_trans_time

    title_source = source_match.group(1).strip()
    question_source = source_match.group(2).strip()
    translation = str(first.get("Translation", "")).strip()
    translation_match = re.match(r"^(60\s+Minutes\s+Rewind)\s+(.+)$", translation, re.I)
    if not translation_match:
        return df_trans_time

    start_idx = int(first.get("start_word_idx", 0))
    end_idx = int(first.get("end_word_idx", start_idx))
    if start_idx + 3 > len(df_words) or end_idx >= len(df_words):
        return df_trans_time

    title_words = [
        _clean_word_token(df_words.iloc[start_idx + offset]["text"])
        for offset in range(3)
    ]
    if title_words != ["60", "minutes", "rewind"]:
        return df_trans_time

    question_start_idx = start_idx + 3
    original_display = first.get("display_timestamp", first.get("speech_timestamp", (None, None)))
    original_display_start = original_display[0] if original_display else None
    original_display_end = original_display[1] if original_display else None

    title_start = float(original_display_start if original_display_start is not None else df_words.iloc[start_idx]["start"])
    title_end = float(df_words.iloc[start_idx + 2]["end"])
    question_start = float(df_words.iloc[question_start_idx]["start"])
    if question_start - title_end < 0.3:
        return df_trans_time

    question_speech_end = float(df_words.iloc[end_idx]["end"])
    question_display_end = float(original_display_end if original_display_end is not None else question_speech_end)

    title_row = dict(first)
    title_row.update({
        "Source": title_source,
        "Translation": translation_match.group(1).strip(),
        "start_word_idx": start_idx,
        "end_word_idx": start_idx + 2,
        "start_word": str(df_words.iloc[start_idx]["text"]).strip('"'),
        "end_word": str(df_words.iloc[start_idx + 2]["text"]).strip('"'),
        "speech_timestamp": (title_start, title_end),
        "display_timestamp": (title_start, title_end),
        "speech_duration": title_end - title_start,
        "duration": title_end - title_start,
        "merged_subtitle_count": 1,
    })

    question_row = dict(first)
    question_row.update({
        "Source": question_source,
        "Translation": translation_match.group(2).strip(),
        "start_word_idx": question_start_idx,
        "end_word_idx": end_idx,
        "start_word": str(df_words.iloc[question_start_idx]["text"]).strip('"'),
        "end_word": str(df_words.iloc[end_idx]["text"]).strip('"'),
        "speech_timestamp": (question_start, question_speech_end),
        "display_timestamp": (question_start, question_display_end),
        "speech_duration": question_speech_end - question_start,
        "duration": question_display_end - question_start,
        "merged_subtitle_count": 1,
    })

    console.print("[blue]ℹ️ Split leading 60 Minutes Rewind title from following question.[/blue]")
    return pd.DataFrame([title_row, question_row] + rows[1:]).reset_index(drop=True)

def _get_video_dimensions(video_file):
    capture = cv2.VideoCapture(video_file)
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        return width, height
    finally:
        capture.release()

def align_timestamp(
    df_text,
    df_translate,
    subtitle_output_configs: list,
    output_dir: str,
    for_display: bool = True,
    write_timing_report: bool = False,
    target_width=None,
    target_height=None,
):
    """Align timestamps and add a new timestamp column to df_translate"""
    df_text = _clean_df_text_asr_artifacts(df_text).reset_index(drop=True)
    df_translate = _clean_sentence_source_artifacts(df_translate).reset_index(drop=True)

    # Assign an ID to each word in df_text['text'] and create a new DataFrame
    words = df_text['text'].str.split(expand=True).stack().reset_index(level=1, drop=True).reset_index()
    words.columns = ['id', 'word']
    words['id'] = words['id'].astype(int)

    # Process timestamps ⏰
    time_info_list = get_sentence_timestamps(df_text, df_translate)
    df_trans_time = df_translate.copy()
    df_trans_time["start_word_idx"] = [item["start_word_idx"] for item in time_info_list]
    df_trans_time["end_word_idx"] = [item["end_word_idx"] for item in time_info_list]
    df_trans_time["start_word"] = [item["start_word"] for item in time_info_list]
    df_trans_time["end_word"] = [item["end_word"] for item in time_info_list]
    df_trans_time["speech_timestamp"] = [_timestamp_dict_to_tuple(item) for item in time_info_list]
    df_trans_time["speech_duration"] = df_trans_time["speech_timestamp"].apply(lambda x: x[1] - x[0])
    df_trans_time = _merge_short_adjacent_subtitles(df_trans_time)
    df_trans_time = _drop_likely_standalone_ack_hallucinations(df_trans_time)
    timing_report_items = _apply_word_anchored_display_timing(df_trans_time)
    if write_timing_report:
        _write_subtitle_timing_report(timing_report_items)
    if for_display and output_dir == _OUTPUT_DIR:
        df_trans_time = _repair_leading_sentence_continuations(df_trans_time, df_text)
        df_trans_time = _split_long_display_subtitles(df_trans_time, target_width, target_height, df_text)
    if for_display:
        df_trans_time = _split_leading_program_title_question(df_trans_time, df_text)
        df_trans_time = _repair_adjacent_source_phrase_splits(df_trans_time)

    # Convert start and end timestamps to SRT format
    df_trans_time['timestamp'] = df_trans_time['display_timestamp'].apply(lambda x: convert_to_srt_format(x[0], x[1]))

    # Polish subtitles: replace punctuation in Translation if for_display
    if for_display:
        df_trans_time['Translation'] = df_trans_time['Translation'].apply(lambda x: re.sub(r'[，。]', ' ', x).strip())

    # Output subtitles 📜

    def _align_bilingual_english(subtitle_str):
        """Re-split English text in bilingual SRT to match Chinese split boundaries.

        Also removes common Whisper hallucination phrases (e.g. "Thank you.",
        "Well.") that appear at the beginning of source lines — these are ASR
        artifacts from mishearing breath or ambient noise as speech.

        Whisper often splits English sentences at different points than where
        Chinese translation naturally breaks. This function detects when the
        Chinese in entry N covers MORE content than the English in entry N
        (because the English was split too early by Whisper), and moves the
        corresponding English text from entry N+1 to entry N.
        """
        import re as _re

        # Common Whisper hallucination phrases at sentence beginnings
        _HALLUCINATION_LEADS = [
            "Thank you.", "Thank you so much.", "Thanks.", "Well.", "So.",
            "OK.", "Okay.", "Yeah.", "Yep.", "Yes.", "No.", "Right.",
            "Absolutely.", "Sure.", "Of course.", "Certainly.",
        ]

        blocks = _re.split(r'\n\n+', subtitle_str.strip())
        if not blocks:
            return subtitle_str

        parsed = []
        halluc_removed = 0
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 4:
                en = lines[3]
                for lead in _HALLUCINATION_LEADS:
                    if en.startswith(lead + ' '):
                        en = en[len(lead):].strip()
                        # Also remove matching hallucination from Chinese
                        cn = lines[2]
                        if lead == 'Thank you.' and cn.startswith('谢谢 '):
                            cn = cn[3:].strip()
                        elif lead in ('Thank you so much.', 'Thanks.') and cn.startswith('谢谢 '):
                            cn = cn[3:].strip()
                        elif lead in ('Well.', 'So.', 'OK.', 'Okay.'):
                            cn = re.sub(r'^[好了那么嗯哦]+\s*', '', cn).strip()
                        lines[2] = cn
                        lines[3] = en
                        halluc_removed += 1
                        break
                parsed.append({
                    'idx': lines[0],
                    'time': lines[1],
                    'cn': lines[2],
                    'en': lines[3],
                })

        if len(parsed) < 2:
            return subtitle_str

        fixed = 0
        for i in range(len(parsed) - 1):
            en_i = parsed[i]['en'].strip()
            en_next = parsed[i+1]['en'].strip()
            cn_i = parsed[i]['cn'].strip()
            cn_next = parsed[i+1]['cn'].strip()

            # Detect: EN_i is a sentence fragment (ends with comma, short relative to next)
            if not en_i.rstrip().endswith(','):
                continue
            if not en_next or not en_next[0].islower():
                continue

            # Fix short orphan words at entry boundary (e.g. "...month he" / "kept calling...")
            # If EN_i ends with a very short lowercase word and EN_next starts
            # with lowercase, pull the orphan word into EN_next.
            # Only applies when EN_i still has ≥ 3 words after removal.
            en_words_i = en_i.split()
            if (len(en_words_i) >= 4
                    and en_words_i[-1].islower()
                    and len(en_words_i[-1]) <= 3
                    and en_next
                    and en_next[0].islower()):
                orphan = en_words_i[-1]
                en_i_new = ' '.join(en_words_i[:-1]).strip().rstrip(',')
                en_next_new = (orphan + ' ' + en_next).strip()
                if en_i_new and en_next_new:
                    parsed[i]['en'] = en_i_new
                    parsed[i+1]['en'] = en_next_new
                    fixed += 1
                    continue

            # Compare proportions: does CN_i cover more of the total than EN_i?
            total_en = len(en_i) + len(en_next)
            total_cn = len(cn_i) + len(cn_next)
            if total_cn == 0:
                continue

            en_share = len(en_i) / total_en
            cn_share = len(cn_i) / total_cn

            # If CN_i has significantly more share, English text needs to move
            if cn_share <= en_share * 1.2:
                continue

            # Compute where to split the combined English
            target_en_i_len = int(total_en * cn_share)
            combined_en = en_i + ' ' + en_next
            words = combined_en.split()

            # Find the word boundary closest to the target length
            cumulative = 0
            split_at = len(words)
            for j, w in enumerate(words):
                cumulative += len(w) + 1
                if cumulative >= target_en_i_len:
                    split_at = j + 1
                    break

            # Avoid breaking multi-word proper nouns across entries
            # (e.g. "Hong | Kong", "San | Francisco", "New | York")
            if 0 < split_at < len(words):
                w_prev = words[split_at - 1]
                w_next = words[split_at]
                if w_prev and w_next and w_prev[0].isupper() and w_next[0].isupper():
                    proper_start = split_at - 1
                    while proper_start > 0:
                        candidate = words[proper_start - 1]
                        if candidate and candidate[0].isupper():
                            proper_start -= 1
                        else:
                            break
                    split_at = proper_start

            if split_at >= len(words):
                continue

            new_en_i = ' '.join(words[:split_at]).strip().rstrip(',')
            new_en_next = ' '.join(words[split_at:]).strip()

            if not new_en_i or not new_en_next:
                continue

            parsed[i]['en'] = new_en_i
            parsed[i+1]['en'] = new_en_next
            fixed += 1

        if fixed or halluc_removed:
            parts = []
            if fixed:
                parts.append(f"re-split English in {fixed} entry pair(s)")
            if halluc_removed:
                parts.append(f"removed {halluc_removed} ASR hallucination(s)")
            console.print(
                f"[blue]\u2139\ufe0f Bilingual SRT post-process: "
                f"{', '.join(parts)}.[/blue]"
            )

        # Rebuild SRT string
        out = []
        for idx, entry in enumerate(parsed):
            out.append(f"{idx+1}\n{entry['time']}\n{entry['cn']}\n{entry['en']}")
        return '\n\n'.join(out) + '\n'

    def generate_subtitle_string(df, columns):
        return ''.join([f"{i+1}\n{row['timestamp']}\n{row[columns[0]].strip()}\n{row[columns[1]].strip() if len(columns) > 1 else ''}\n\n" for i, row in df.iterrows()]).strip()

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        for filename, columns in subtitle_output_configs:
            subtitle_str = generate_subtitle_string(df_trans_time, columns)
            with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(subtitle_str)

    return df_trans_time

    # ✨ Beautify the translation
def clean_translation(x):
    if pd.isna(x):
        return ''
    cleaned = clean_prompt_pollution(x).strip('。').strip('，')
    return normalize_cjk_latin_spacing(autocorrect.format(cleaned))

def _normalize_for_match(text):
    text = re.sub(r"\s+", " ", str(text).strip()).lower()
    text = re.sub(r"[^\w\s\u4e00-\u9fff]", "", text)
    return text.strip()

def _srt_start_seconds(timestamp):
    match = re.match(r"(\d+):(\d+):(\d+),(\d+)", str(timestamp or ""))
    if not match:
        return None
    hours, minutes, seconds, milliseconds = [int(item) for item in match.groups()]
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000

def _find_row_by_timestamp(df_trans_time, timestamp):
    target_start = _srt_start_seconds(timestamp)
    if target_start is None:
        return None, None

    best = (None, None, float("inf"))
    for row_index, row in df_trans_time.iterrows():
        row_start = _srt_start_seconds(row.get("timestamp", ""))
        if row_start is None:
            continue
        delta = abs(row_start - target_start)
        if delta < best[2]:
            best = (row_index, row, delta)
    if best[2] <= 2.0:
        return best[0], best[1]
    return None, None

def _strip_leading_ack_for_match(text):
    return _normalize_for_match(LEADING_ACK_RE.sub("", str(text), count=1))

def _find_source_matches(rows_by_source, source_key):
    source_matches = rows_by_source.get(source_key, [])
    if source_matches:
        return source_matches

    stripped_source_key = _strip_leading_ack_for_match(source_key)
    if not stripped_source_key or stripped_source_key == source_key:
        return []

    partial_matches = []
    for row_source_key, row_matches in rows_by_source.items():
        if row_source_key and (row_source_key in stripped_source_key or stripped_source_key in row_source_key):
            partial_matches.extend(row_matches)
    if partial_matches:
        return partial_matches

    fuzzy_matches = []
    for row_source_key, row_matches in rows_by_source.items():
        if not row_source_key:
            continue
        score = SequenceMatcher(None, source_key, row_source_key).ratio()
        if score >= 0.62:
            fuzzy_matches.extend((score, match) for match in row_matches)
    fuzzy_matches.sort(key=lambda item: item[0], reverse=True)
    return [match for _, match in fuzzy_matches]

def write_ambiguity_report(df_trans_time):
    if not load_key("enable_ambiguity_check"):
        for report_path in (_4_3_AMBIGUITY, AMBIGUITY_REPORT_MD):
            if os.path.exists(report_path):
                os.remove(report_path)
        return

    if not os.path.exists(_4_3_AMBIGUITY):
        return
    try:
        with open(_4_3_AMBIGUITY, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception:
        return
    if not items:
        return

    rows_by_source = {}
    for row_index, row in df_trans_time.iterrows():
        rows_by_source.setdefault(_normalize_for_match(row["Source"]), []).append((row_index, row))

    original_rows_by_source = {}
    if os.path.exists(_4_2_TRANSLATION):
        try:
            df_original_time = pd.read_excel(_4_2_TRANSLATION)
            for row_index, row in df_original_time.iterrows():
                original_rows_by_source.setdefault(_normalize_for_match(row["Source"]), []).append((row_index, row))
        except Exception:
            original_rows_by_source = {}

    used_sources = {}
    report_items = []
    for item in items:
        source_key = _normalize_for_match(item.get("source", ""))
        source_matches = _find_source_matches(rows_by_source, source_key)
        used_index = used_sources.get(source_key, 0)
        row_match = source_matches[used_index] if used_index < len(source_matches) else (None, None)
        used_sources[source_key] = used_index + 1
        row_index, row = row_match
        enriched = dict(item)
        original_timestamp = ""
        if row is None and original_rows_by_source:
            original_matches = _find_source_matches(original_rows_by_source, source_key)
            original_row = original_matches[0][1] if original_matches else None
            if original_row is not None:
                original_timestamp = original_row.get("timestamp", "")
                row_index, row = _find_row_by_timestamp(df_trans_time, original_timestamp)

        if row is not None:
            enriched["subtitle_index"] = int(row_index) + 1
            enriched["timestamp"] = row.get("timestamp", "")
            enriched["translation"] = row.get("Translation", enriched.get("translation", ""))
        elif original_timestamp:
            enriched["subtitle_index"] = enriched.get("subtitle_index") or "原始句"
            enriched["timestamp"] = original_timestamp
        report_items.append(enriched)

    with open(_4_3_AMBIGUITY, "w", encoding="utf-8") as f:
        json.dump(report_items, f, ensure_ascii=False, indent=2)

    lines = ["# Ambiguity Review Report", ""]
    for index, item in enumerate(report_items, start=1):
        subtitle_index = item.get('subtitle_index', '?')
        timestamp = item.get('timestamp') or '时间戳未匹配'
        lines.extend([
            f"## {index}. 字幕 {subtitle_index} · {timestamp}",
            f"- Source: {item.get('source', '')}",
            f"- Translation: {item.get('translation', '')}",
            f"- Ambiguity: {item.get('ambiguity', '')}",
            f"- Reason: {item.get('reason', '')}",
            "",
        ])
    with open(AMBIGUITY_REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

def align_timestamp_main():
    df_text = pd.read_excel(_2_CLEANED_CHUNKS)
    df_text['text'] = df_text['text'].str.strip('"').str.strip()
    df_translate = pd.read_excel(_5_SPLIT_SUB)
    df_translate['Translation'] = df_translate['Translation'].apply(clean_translation)

    video_file = find_video_files()
    target_width, target_height = _get_video_dimensions(video_file)
    subtitle_paths = get_default_subtitle_paths(video_file, _OUTPUT_DIR)
    subtitle_output_configs = [
        (os.path.basename(subtitle_paths[key]), columns)
        for key, columns in SUBTITLE_OUTPUT_CONFIG_KEYS
    ]
    df_trans_time = align_timestamp(
        df_text,
        df_translate,
        subtitle_output_configs,
        _OUTPUT_DIR,
        write_timing_report=True,
        target_width=target_width,
        target_height=target_height,
    )
    if load_key("enable_subtitle_proofread"):
        proofread_subtitle_set(
            subtitle_paths,
            report_json=SUBTITLE_PROOFREAD_REPORT_JSON,
            report_md=SUBTITLE_PROOFREAD_REPORT_MD,
            auto_fix=True,
        )
    else:
        clear_subtitle_proofread_report()
    write_ambiguity_report(df_trans_time)
    console.print(Panel("[bold green]🎉📝 Subtitles generation completed! Please check in the `output` folder 👀[/bold green]"))

    # for audio
    df_translate_for_audio = pd.read_excel(_5_REMERGED) # use remerged file to avoid unmatched lines when dubbing
    df_translate_for_audio['Translation'] = df_translate_for_audio['Translation'].apply(clean_translation)

    align_timestamp(df_text, df_translate_for_audio, AUDIO_SUBTITLE_OUTPUT_CONFIGS, _AUDIO_DIR)
    console.print(Panel(f"[bold green]🎉📝 Audio subtitles generation completed! Please check in the `{_AUDIO_DIR}` folder 👀[/bold green]"))


if __name__ == '__main__':
    align_timestamp_main()
