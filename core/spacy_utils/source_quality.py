import json
import os
import re
from typing import Iterable, List, Tuple

from rich.console import Console

console = Console()

SOURCE_SEGMENT_QUALITY_JSON = "output/log/source_segment_quality_report.json"
SOURCE_SEGMENT_QUALITY_MD = "output/log/source_segment_quality_report.md"

QUESTION_STARTERS = (
    "What", "Where", "When", "Why", "Who", "Whom", "Whose", "Which", "How",
    "Did", "Do", "Does", "Can", "Could", "Would", "Will", "Is", "Are", "Was",
    "Were", "Have", "Has", "Had",
)

ANSWER_BOUNDARY_WORDS = (
    "say", "tell", "know", "remember", "answer", "understand", "sure",
    "mean", "think", "guess",
)

HANGING_END_WORDS = {
    "a", "an", "the",
    "to", "of", "for", "with", "without", "from", "in", "on", "at", "by",
    "and", "or", "but", "so", "because", "if", "when", "while", "although",
    "that", "which", "who", "whom", "whose",
    "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did",
    "have", "has", "had",
    "will", "would", "can", "could", "should", "may", "might", "must",
    "not", "n't",
    "my", "your", "his", "her", "our", "their",
}


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?", str(text)))


def _last_word(text: str) -> str:
    words = re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)?", str(text).lower())
    return words[-1] if words else ""


def _ends_with_sentence_punctuation(text: str) -> bool:
    return bool(re.search(r"[.!?。！？…]['\")\]]*$", str(text).strip()))


def _split_embedded_dialogue_question(line: str) -> List[str]:
    text = re.sub(r"\s+", " ", str(line)).strip()
    if not text:
        return []

    starters = "|".join(map(re.escape, QUESTION_STARTERS))
    boundary_words = "|".join(map(re.escape, ANSWER_BOUNDARY_WORDS))
    pattern = re.compile(
        rf"^(.+?\b(?:{boundary_words}))\s+(({starters})\b.+\?)$"
    )
    match = pattern.match(text)
    if not match:
        return [text]

    left = match.group(1).strip()
    right = match.group(2).strip()
    if not left or not right:
        return [text]

    if _ends_with_sentence_punctuation(left):
        first = left
    else:
        first = f"{left}."
    return [first, right]


def _is_terminal_hanging_fragment(line: str) -> bool:
    text = re.sub(r"\s+", " ", str(line)).strip()
    if not text or _ends_with_sentence_punctuation(text):
        return False
    return _word_count(text) <= 8 and _last_word(text) in HANGING_END_WORDS


def postprocess_source_segments(lines: Iterable[str]) -> Tuple[List[str], List[dict]]:
    raw_lines = [re.sub(r"\s+", " ", str(line)).strip() for line in lines]
    raw_lines = [line for line in raw_lines if line]
    processed = []
    report = []

    for index, line in enumerate(raw_lines, start=1):
        split_lines = _split_embedded_dialogue_question(line)
        if len(split_lines) > 1:
            report.append({
                "type": "embedded_question_split",
                "line_index": index,
                "source": line,
                "replacement": split_lines,
                "reason": "A capitalized question starts after a short answer phrase; treat it as a separate subtitle sentence.",
            })
        processed.extend(split_lines)

    if processed and _is_terminal_hanging_fragment(processed[-1]):
        removed = processed.pop()
        report.append({
            "type": "terminal_hanging_fragment_removed",
            "line_index": len(raw_lines),
            "source": removed,
            "reason": "The final ASR segment ends with a function word and has no sentence-ending punctuation.",
        })

    return processed, report


def write_source_segment_quality_report(items: List[dict]):
    for path in (SOURCE_SEGMENT_QUALITY_JSON, SOURCE_SEGMENT_QUALITY_MD):
        if not items and os.path.exists(path):
            os.remove(path)
    if not items:
        return

    os.makedirs(os.path.dirname(SOURCE_SEGMENT_QUALITY_JSON), exist_ok=True)
    with open(SOURCE_SEGMENT_QUALITY_JSON, "w", encoding="utf-8") as f:
        json.dump({"summary": {"item_count": len(items)}, "items": items}, f, ensure_ascii=False, indent=2)

    lines = ["# Source Segment Quality Report", "", f"- item_count: {len(items)}", ""]
    for index, item in enumerate(items, start=1):
        lines.extend([
            f"## {index}. {item['type']}",
            f"- Source: {item.get('source', '')}",
            f"- Replacement: {item.get('replacement', '')}",
            f"- Reason: {item.get('reason', '')}",
            "",
        ])
    with open(SOURCE_SEGMENT_QUALITY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

    console.print(f"[yellow]⚠️ Source segment quality report saved to {SOURCE_SEGMENT_QUALITY_MD}[/yellow]")


def postprocess_source_segments_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines()]
    processed, report = postprocess_source_segments(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(processed))
    write_source_segment_quality_report(report)
    return report
