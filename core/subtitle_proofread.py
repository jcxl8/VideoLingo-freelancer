import re
from pathlib import Path

from core.translate_lines import translation_may_omit_content
from core.utils.atomic_files import atomic_write_json, atomic_write_text


SUBTITLE_PROOFREAD_REPORT_JSON = "output/log/subtitle_proofread_report.json"
SUBTITLE_PROOFREAD_REPORT_MD = "output/subtitle_proofread_report.md"

_TIMESTAMP = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s+-->\s+"
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})$"
)
_SHORT_LOWERCASE_FRAGMENT = re.compile(r"^[a-z][A-Za-z'’-]*(?:\s+[a-z][A-Za-z'’-]*){0,4}[.!?,…]*$")
_SUSPICIOUS_INLINE_ELLIPSIS = re.compile(r"\b[A-Za-z]+\.\.\.\s+[a-z]")
_SHORT_FILLER_SOURCE = re.compile(r"^(?:you know\?|yeah\.?|right,?|okay\.?|ok\.?|all right\.?)$", re.I)
_SHORT_SELF_INTRO_SOURCE = re.compile(r"^i['’]?m\s+[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+){0,3}\.?$", re.I)
_COUNT_TAIL_TRANSLATION = re.compile(r"(?:\d+|一|二|两|三|四|五|六|七|八|九|十|几|多).{0,4}(?:次|遍|条|个|档|回|左右|大概)|(?:十|10)")
_CHINESE_SELF_INTRO_TAIL = re.compile(r"((?:我是|我叫|这里是).+)$")


def _target_has_question_marker(text):
    return bool(re.search(r"[？?吗呢]|什么|怎么|为什么|如何|谁|哪|是否|懂|知道|对吧|是吧", str(text)))


def _seconds(parts):
    hours, minutes, seconds, milliseconds = (int(value) for value in parts)
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def _parse_srt(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    content = path.read_text(encoding="utf-8-sig").strip()
    if not content:
        return []
    entries = []
    for block_number, block in enumerate(re.split(r"\r?\n\s*\r?\n", content), 1):
        lines = block.splitlines()
        if len(lines) < 3:
            raise ValueError(f"block {block_number} is incomplete")
        try:
            index = int(lines[0].strip())
        except ValueError as exc:
            raise ValueError(f"block {block_number} has an invalid index") from exc
        match = _TIMESTAMP.match(lines[1].strip())
        if not match:
            raise ValueError(f"block {block_number} has an invalid timestamp")
        entries.append({
            "index": index,
            "start": _seconds(match.groups()[:4]),
            "end": _seconds(match.groups()[4:]),
            "timestamp": lines[1].strip(),
            "lines": lines[2:],
            "text": "\n".join(lines[2:]).strip(),
        })
    return entries


def _normalise(text):
    return re.sub(r"\s+", " ", str(text)).strip()


def _format_seconds(seconds):
    milliseconds = int(round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3600 * 1000)
    minutes, remainder = divmod(remainder, 60 * 1000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def _write_srt(path, entries, line_builder):
    blocks = []
    for entry in entries:
        lines = line_builder(entry)
        text = "\n".join(line for line in lines if line is not None)
        blocks.append(f"{entry['index']}\n{_format_seconds(entry['start'])} --> {_format_seconds(entry['end'])}\n{text}")
    atomic_write_text(path, "\n\n".join(blocks) + "\n")


def _write_subtitle_set(paths, source_entries, translation_entries):
    _write_srt(paths["src"], source_entries, lambda entry: entry["lines"])
    _write_srt(paths["trans"], translation_entries, lambda entry: entry["lines"])
    _write_srt(paths["src_trans"], source_entries, lambda entry: [
        source_entries[entry["index"] - 1]["text"],
        translation_entries[entry["index"] - 1]["text"],
    ])
    _write_srt(paths["trans_src"], source_entries, lambda entry: [
        translation_entries[entry["index"] - 1]["text"],
        source_entries[entry["index"] - 1]["text"],
    ])


def _set_entry_text(entry, text):
    entry["lines"] = [text]
    entry["text"] = text


def _append_entry_text(entry, text):
    text = _normalise(text)
    if not text:
        return
    current = _normalise(entry["text"])
    if text in current:
        return
    _set_entry_text(entry, _normalise(f"{current} {text}"))


def _auto_fix_translation_alignment(source_entries, translation_entries):
    fixes = []
    limit = min(len(source_entries), len(translation_entries))
    for position in range(limit):
        source_text = _normalise(source_entries[position]["text"])
        translation_text = _normalise(translation_entries[position]["text"])
        if (
            source_text.lower() == "you know?"
            and len(translation_text) > 8
            and not _target_has_question_marker(translation_text)
            and position + 1 < limit
        ):
            _append_entry_text(translation_entries[position + 1], translation_text)
            _set_entry_text(translation_entries[position], "你懂吧？")
            fixes.append({
                "entry_index": translation_entries[position]["index"],
                "type": "auto_fixed_short_question_shift",
                "reason": "Moved non-question translation from a standalone 'You know?' subtitle to the following entry.",
            })
            continue
        if _SHORT_SELF_INTRO_SOURCE.fullmatch(source_text) and _COUNT_TAIL_TRANSLATION.search(translation_text):
            match = _CHINESE_SELF_INTRO_TAIL.search(translation_text)
            if match and position > 0:
                shifted_text = translation_text[:match.start()].strip(" ，,。")
                self_intro_text = match.group(1).strip()
                if shifted_text and self_intro_text:
                    _append_entry_text(translation_entries[position - 1], shifted_text)
                    _set_entry_text(translation_entries[position], self_intro_text)
                    fixes.append({
                        "entry_index": translation_entries[position]["index"],
                        "type": "auto_fixed_self_intro_tail_shift",
                        "reason": "Moved count phrase from a short self-introduction subtitle back to the preceding entry.",
                    })
    return fixes


def _issue(issue_type, reason, *, severity="warning", entry=None, source="", translation=""):
    return {
        "severity": severity,
        "type": issue_type,
        "entry_index": entry["index"] if entry else None,
        "timestamp": entry["timestamp"] if entry else "",
        "source": source,
        "translation": translation,
        "reason": reason,
    }


def _render_markdown(report):
    summary = report["summary"]
    lines = [
        "# Subtitle Proofread Report",
        "",
        f"Status: {report['status']}",
        f"Entries: {summary['entry_count']}",
        f"Issues: {summary['issue_count']} (errors: {summary['error_count']}, warnings: {summary['warning_count']})",
        "",
    ]
    for item in report["issues"]:
        location = f"entry {item['entry_index']}" if item["entry_index"] is not None else "subtitle set"
        lines.extend([
            f"## [{item['severity']}] {item['type']} — {location}",
            "",
            item["reason"],
            "",
        ])
        if item["source"]:
            lines.append(f"- Source: {item['source']}")
        if item["translation"]:
            lines.append(f"- Translation: {item['translation']}")
        if item["source"] or item["translation"]:
            lines.append("")
    return "\n".join(lines)


def proofread_subtitle_set(paths, report_json=None, report_md=None, auto_fix=False):
    """Audit final SRT variants without modifying them."""
    required = ("src", "trans", "src_trans", "trans_src")
    parsed = {}
    issues = []
    for key in required:
        try:
            parsed[key] = _parse_srt(paths[key])
        except (KeyError, OSError, ValueError) as exc:
            parsed[key] = []
            issues.append(_issue("srt_parse_error", f"{key}: {exc}", severity="error"))

    counts = {key: len(entries) for key, entries in parsed.items()}
    if len(set(counts.values())) > 1:
        issues.append(_issue(
            "entry_count_mismatch",
            "Subtitle variants have different entry counts: " + ", ".join(f"{key}={value}" for key, value in counts.items()),
            severity="error",
        ))
    fixes = []
    if auto_fix and not issues and parsed["src"] and parsed["trans"]:
        fixes = _auto_fix_translation_alignment(parsed["src"], parsed["trans"])
        if fixes:
            _write_subtitle_set(paths, parsed["src"], parsed["trans"])
            parsed = {key: _parse_srt(paths[key]) for key in required}
            counts = {key: len(entries) for key, entries in parsed.items()}

    for key, entries in parsed.items():
        previous = None
        for position, entry in enumerate(entries, 1):
            if entry["index"] != position:
                issues.append(_issue("non_continuous_index", f"{key} expected index {position}.", severity="error", entry=entry))
            if entry["start"] >= entry["end"]:
                issues.append(_issue("invalid_duration", f"{key} start time must be before end time.", severity="error", entry=entry))
            if previous and entry["start"] < previous["end"] - 0.001:
                issues.append(_issue("timestamp_overlap", f"{key} overlaps the preceding subtitle.", severity="error", entry=entry))
            if not entry["text"]:
                issues.append(_issue("empty_text", f"{key} contains an empty subtitle.", severity="error", entry=entry))
            previous = entry

    source_entries = parsed["src"]
    translation_entries = parsed["trans"]
    for position in range(min(len(source_entries), len(translation_entries))):
        source = source_entries[position]
        translation = translation_entries[position]
        source_text = _normalise(source["text"])
        translation_text = _normalise(translation["text"])
        if abs(source["start"] - translation["start"]) > 0.002 or abs(source["end"] - translation["end"]) > 0.002:
            issues.append(_issue("timestamp_mismatch", "Source and translation timestamps differ.", severity="error", entry=source, source=source_text, translation=translation_text))
        if _SHORT_LOWERCASE_FRAGMENT.fullmatch(source_text):
            issues.append(_issue("source_fragment", "Short lowercase source fragment may have been split from the preceding sentence.", entry=source, source=source_text, translation=translation_text))
        if _SUSPICIOUS_INLINE_ELLIPSIS.search(source_text):
            issues.append(_issue("asr_suspicion", "Unexpected ellipsis inside a source phrase; verify this passage against the audio.", entry=source, source=source_text, translation=translation_text))
        duration = max(translation["end"] - translation["start"], 0.001)
        visible_characters = len(re.sub(r"\s+", "", translation_text))
        if visible_characters / duration > 13:
            issues.append(_issue("translation_cps", "Translation reading speed exceeds 13 visible characters per second.", entry=translation, source=source_text, translation=translation_text))
        if translation_may_omit_content(source_text, translation_text):
            issues.append(_issue("translation_omission", "Translation may omit part of the source subtitle.", severity="error", entry=translation, source=source_text, translation=translation_text))
        if _SHORT_FILLER_SOURCE.fullmatch(source_text) and len(translation_text) > 8:
            issues.append(_issue("semantic_alignment_suspicion", "Very short filler/question source is paired with a long translation; adjacent subtitle text may be shifted.", severity="error", entry=translation, source=source_text, translation=translation_text))
        if _SHORT_SELF_INTRO_SOURCE.fullmatch(source_text) and _COUNT_TAIL_TRANSLATION.search(translation_text):
            issues.append(_issue("semantic_alignment_suspicion", "Short self-introduction source is paired with a count phrase; preceding subtitle text may be shifted into this entry.", severity="error", entry=translation, source=source_text, translation=translation_text))
        if "?" in source_text and not _target_has_question_marker(translation_text):
            issues.append(_issue("question_translation_mismatch", "Source is a question but the translation has no question marker.", entry=translation, source=source_text, translation=translation_text))

    expectations = {
        "src_trans": lambda source, translation: [source, translation],
        "trans_src": lambda source, translation: [translation, source],
    }
    for key, build_expected in expectations.items():
        entries = parsed[key]
        for position in range(min(len(entries), len(source_entries), len(translation_entries))):
            entry = entries[position]
            source_text = _normalise(source_entries[position]["text"])
            translation_text = _normalise(translation_entries[position]["text"])
            expected = build_expected(source_text, translation_text)
            actual = [_normalise(line) for line in entry["lines"]]
            if actual != expected:
                issues.append(_issue("bilingual_text_mismatch", f"{key} does not mirror the canonical source and translation text/order.", severity="error", entry=entry, source=source_text, translation=translation_text))
            canonical = source_entries[position]
            if abs(entry["start"] - canonical["start"]) > 0.002 or abs(entry["end"] - canonical["end"]) > 0.002:
                issues.append(_issue("bilingual_timestamp_mismatch", f"{key} timestamp differs from the canonical subtitle.", severity="error", entry=entry, source=source_text, translation=translation_text))

    error_count = sum(item["severity"] == "error" for item in issues)
    report = {
        "version": 1,
        "status": "issues_found" if issues else "passed",
        "summary": {
            "entry_count": len(source_entries),
            "issue_count": len(issues),
            "error_count": error_count,
            "warning_count": len(issues) - error_count,
            "fix_count": len(fixes),
        },
        "files": {key: str(paths.get(key, "")) for key in required},
        "fixes": fixes,
        "issues": issues,
    }
    if report_json:
        atomic_write_json(report_json, report, indent=2)
    if report_md:
        atomic_write_text(report_md, _render_markdown(report))
    return report


def load_subtitle_proofread_report(path=SUBTITLE_PROOFREAD_REPORT_JSON):
    import json

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def clear_subtitle_proofread_report():
    for path in (SUBTITLE_PROOFREAD_REPORT_JSON, SUBTITLE_PROOFREAD_REPORT_MD):
        Path(path).unlink(missing_ok=True)
