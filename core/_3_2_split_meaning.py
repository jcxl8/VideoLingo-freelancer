import concurrent.futures
from difflib import SequenceMatcher
import math
import json
import os
import re
from core.prompts import get_split_prompt
from core.spacy_utils.load_nlp_model import init_nlp
from core.spacy_utils.source_quality import postprocess_source_segments, write_source_segment_quality_report
from core.utils import *
from rich.console import Console
from rich.table import Table
from core.utils.models import _3_1_SPLIT_BY_NLP, _3_2_SPLIT_BY_MEANING, _3_2_SEGMENTATION_REPORT, _3_2_SEGMENTATION_REPORT_MD
console = Console()

CONTINUATION_START_RE = re.compile(
    r"^\s*(?:[,.;:!?]+|(?:a|an|the|of|to|in|on|at|by|for|from|with|without|and|or|but|so|as|if|when|while|although|because|that|which|who|where|not|then)\b)",
    re.I,
)
# =========================
# 数字保护：防止把 "1,500" 这类数字误拆
# =========================

_NUMBER_COMMA_RE = re.compile(r"(?<=\d),(?=\d)")

def _normalize_numbers_for_counting(text: str) -> str:
    """将数字中的逗号移除（如 1,500 → 1500），避免被 spaCy 切成多个 token。"""
    return _NUMBER_COMMA_RE.sub("", str(text))

def _split_breaks_number(split_lines: list) -> bool:
    """检查拆分后的各行是否切断了数字（如 "almost 1" / "000 robots"）。"""
    if len(split_lines) < 2:
        return False
    for i in range(len(split_lines) - 1):
        prev_end = split_lines[i].strip()
        next_start = split_lines[i + 1].strip().lstrip(",.;:!?，。；：！？ ")
        # 上一行以数字结尾
        prev_ends_digit = bool(re.search(r"\d\s*$", prev_end))
        # 下一行以数字（或逗号+数字）开头
        next_starts_digit = bool(re.match(r"^[,]?\d+", next_start))
        if prev_ends_digit and next_starts_digit:
            return True
    return False



def _word_count(text):
    return len(re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", str(text)))

def _edge_token(text, first=False):
    tokens = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", str(text).lower())
    if not tokens:
        return ""
    return tokens[0] if first else tokens[-1]

def write_segmentation_quality_report(sentences):
    try:
        min_words = int(load_key("min_split_source_words"))
    except Exception:
        min_words = 10
    try:
        max_length = int(load_key("max_split_length"))
    except Exception:
        max_length = 20

    items = []
    for index, sentence in enumerate(sentences):
        words = _word_count(sentence)
        if words and words < min_words:
            items.append({
                "index": index + 1,
                "type": "short_segment",
                "word_count": words,
                "source": sentence,
                "reason": f"Segment has fewer than {min_words} English words; check if it was over-split.",
            })
        if words > max_length * 1.5:
            items.append({
                "index": index + 1,
                "type": "long_segment",
                "word_count": words,
                "source": sentence,
                "reason": "Segment is much longer than the configured split length.",
            })
        if CONTINUATION_START_RE.search(str(sentence)):
            items.append({
                "index": index + 1,
                "type": "continuation_start",
                "word_count": words,
                "source": sentence,
                "reason": "Segment starts with a connector or punctuation; it may belong to the previous segment.",
            })
        if index > 0:
            previous_last = _edge_token(sentences[index - 1])
            current_first = _edge_token(sentence, first=True)
            if previous_last and current_first and previous_last == current_first:
                items.append({
                    "index": index + 1,
                    "type": "duplicate_boundary_word",
                    "word": current_first,
                    "source": sentence,
                    "reason": "The previous segment ends with the same word this segment starts with.",
                })

    for path in (_3_2_SEGMENTATION_REPORT, _3_2_SEGMENTATION_REPORT_MD):
        if not items and os.path.exists(path):
            os.remove(path)
    if not items:
        return []

    report = {"summary": {"item_count": len(items), "segment_count": len(sentences)}, "items": items}
    with open(_3_2_SEGMENTATION_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    lines = ["# Segmentation Quality Report", "", f"- segment_count: {len(sentences)}", f"- item_count: {len(items)}", ""]
    for item in items[:120]:
        lines.extend([
            f"## {item['index']}. {item['type']}",
            f"- Source: {item.get('source', '')}",
            f"- Reason: {item.get('reason', '')}",
            "",
        ])
    with open(_3_2_SEGMENTATION_REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    console.print(f"[yellow]⚠️ Segmentation quality report saved to {_3_2_SEGMENTATION_REPORT_MD}[/yellow]")
    return items

def tokenize_sentence(sentence, nlp):
    doc = nlp(sentence)
    return [token.text for token in doc]

def find_split_positions(original, modified):
    split_positions = []
    parts = modified.split('[br]')
    start = 0
    whisper_language = load_key("whisper.language")
    language = load_key("whisper.detected_language") if whisper_language == 'auto' else whisper_language
    joiner = get_joiner(language)

    for i in range(len(parts) - 1):
        max_similarity = 0
        best_split = None

        for j in range(start, len(original)):
            original_left = original[start:j]
            modified_left = joiner.join(parts[i].split())

            left_similarity = SequenceMatcher(None, original_left, modified_left).ratio()

            if left_similarity > max_similarity:
                max_similarity = left_similarity
                best_split = j

        if max_similarity < 0.9:
            console.print(f"[yellow]Warning: low similarity found at the best split point: {max_similarity}[/yellow]")
        if best_split is not None:
            split_positions.append(best_split)
            start = best_split
        else:
            console.print(f"[yellow]Warning: Unable to find a suitable split point for the {i+1}th part.[/yellow]")

    return split_positions

def split_sentence(sentence, num_parts, word_limit=20, index=-1, retry_attempt=0):
    """Split a long sentence using GPT and return the result as a string."""
    split_prompt = get_split_prompt(sentence, num_parts, word_limit)
    def valid_split(response_data):
        choice = response_data["choice"]
        if f'split{choice}' not in response_data:
            return {"status": "error", "message": "Missing required key: `split`"}
        if "[br]" not in response_data[f"split{choice}"]:
            return {"status": "error", "message": "Split failed, no [br] found"}
        return {"status": "success", "message": "Split completed"}
    
    response_data = ask_gpt(split_prompt + " " * retry_attempt, resp_type='json', valid_def=valid_split, log_title='split_by_meaning')
    choice = response_data["choice"]
    best_split = response_data[f"split{choice}"]
    split_points = find_split_positions(sentence, best_split)
    # split the sentence based on the split points
    for i, split_point in enumerate(split_points):
        if i == 0:
            best_split = sentence[:split_point] + '\n' + sentence[split_point:]
        else:
            parts = best_split.split('\n')
            last_part = parts[-1]
            parts[-1] = last_part[:split_point - split_points[i-1]] + '\n' + last_part[split_point - split_points[i-1]:]
            best_split = '\n'.join(parts)
    if index != -1:
        console.print(f'[green]✅ Sentence {index} has been successfully split[/green]')
    table = Table(title="")
    table.add_column("Type", style="cyan")
    table.add_column("Sentence")
    table.add_row("Original", sentence, style="yellow")
    table.add_row("Split", best_split.replace('\n', ' ||'), style="yellow")
    console.print(table)
    
    return best_split

def parallel_split_sentences(sentences, max_length, max_workers, nlp, retry_attempt=0):
    """Split sentences in parallel using a thread pool."""
    new_sentences = [None] * len(sentences)
    futures = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for index, sentence in enumerate(sentences):
            # Use tokenizer to split the sentence
            # 先对数字做归一化（移除数字内逗号），避免 "1,500" 被切成 3 个 token 导致误拆
            normalized = _normalize_numbers_for_counting(sentence)
            tokens = tokenize_sentence(normalized, nlp)
            num_parts = math.ceil(len(tokens) / max_length)
            if len(tokens) > max_length:
                future = executor.submit(split_sentence, sentence, num_parts, max_length, index=index, retry_attempt=retry_attempt)
                futures.append((future, index, num_parts, sentence))
            else:
                new_sentences[index] = [sentence]

        for future, index, num_parts, sentence in futures:
            split_result = future.result()
            if split_result:
                split_lines = split_result.strip().split('\n')
                # 检查 GPT 是否切断了数字（如 "1,500" 被切成 "1" / "500"）
                if _split_breaks_number(split_lines):
                    console.print(
                        f"[yellow]⚠️ GPT split broke a number in sentence {index}; "
                        f"keeping original sentence unsplit.[/yellow]"
                    )
                    new_sentences[index] = [sentence]
                else:
                    new_sentences[index] = [line.strip() for line in split_lines]
            else:
                new_sentences[index] = [sentence]

    return [sentence for sublist in new_sentences for sentence in sublist]

def split_sentences_by_meaning():
    """The main function to split sentences by meaning."""
    # read input sentences
    with open(_3_1_SPLIT_BY_NLP, 'r', encoding='utf-8') as f:
        sentences = [line.strip() for line in f.readlines()]

    nlp = init_nlp()
    # 🔄 process sentences multiple times to ensure all are split
    for retry_attempt in range(3):
        sentences = parallel_split_sentences(sentences, max_length=load_key("max_split_length"), max_workers=load_key("max_workers"), nlp=nlp, retry_attempt=retry_attempt)

    sentences, source_quality_items = postprocess_source_segments(sentences)
    write_source_segment_quality_report(source_quality_items)

    # 💾 save results
    with open(_3_2_SPLIT_BY_MEANING, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sentences))
    write_segmentation_quality_report(sentences)
    console.print('[green]✅ All sentences have been successfully split![/green]')

if __name__ == '__main__':
    # print(split_sentence('Which makes no sense to the... average guy who always pushes the character creation slider all the way to the right.', 2, 22))
    split_sentences_by_meaning()
