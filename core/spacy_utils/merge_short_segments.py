import re
import os
from typing import List

import pandas as pd

from rich.console import Console
from rich.table import Table

from core.utils.models import _2_CLEANED_CHUNKS, _3_1_SPLIT_BY_NLP

console = Console()


# =========================
# 可调参数
# =========================

# 少于这个词数，优先视为过短碎片
MIN_WORDS = 5

# 少于这个字符数，优先视为过短碎片
MIN_CHARS = 16

# 合并后的单行最大字符数
# 不宜太大，否则后面 _3_2_split_meaning.py 还会重新拆
MAX_MERGED_CHARS = 130

# 明确是延续片段时允许稍长，后续 _3_2_split_meaning.py 仍会按语义再拆。
MAX_CONTINUATION_MERGED_CHARS = 180
MAX_CONTINUATION_MERGED_WORDS = 32

# 连续最多合并多少行
# 防止一口气把很多句子合成一个超长段落
MAX_MERGE_LINES = 5

# Never combine subtitle clauses across a real speech pause this long. Short
# complete sentences are otherwise deliberately merged below, which can make
# a translator drop one clause when two separate shots are treated as one.
PAUSE_PROTECTED_BOUNDARY_SECONDS = 1.5
NONREPEATABLE_DUPLICATE_WORDS = {
    "a", "an", "the",
    "of", "to", "in", "on", "at", "by", "for", "from", "with", "without",
}
NONREPEATABLE_DUPLICATE_RE = re.compile(
    r"\b("
    + "|".join(sorted(map(re.escape, NONREPEATABLE_DUPLICATE_WORDS), key=len, reverse=True))
    + r")\b(?:\s+\1\b)+",
    re.I,
)
ASR_PHRASE_CORRECTIONS = [
    (re.compile(r"\bwon\s+wanted\b", re.I), "wanted"),
    (re.compile(r"\bnational\s+all\b", re.I), "National Mall"),
    (re.compile(r"\bAfrica[\s.]+Americans\b", re.I), "African Americans"),
]


# =========================
# 基础清洗函数
# =========================

def normalize_space(text: str) -> str:
    """
    压缩多余空格。
    """
    return re.sub(r"\s+", " ", str(text)).strip()


def collapse_nonrepeatable_duplicates(text: str) -> str:
    return NONREPEATABLE_DUPLICATE_RE.sub(lambda match: match.group(1), str(text))


def apply_asr_phrase_corrections(text: str) -> str:
    corrected = str(text)
    for pattern, replacement in ASR_PHRASE_CORRECTIONS:
        corrected = pattern.sub(replacement, corrected)
    return corrected


def fix_broken_words(text: str) -> str:
    """
    修复少数被错误切开的英文单词。
    例如：
    Ab solutely -> Absolutely

    注意：
    这里只处理非常明确的断词情况。
    不建议写得太激进，否则可能误改正常字幕。
    """
    replacements = {
        "Ab solutely": "Absolutely",
        "ab solutely": "absolutely",
    }

    for wrong, right in replacements.items():
        text = text.replace(wrong, right)

    text = collapse_nonrepeatable_duplicates(text)
    return apply_asr_phrase_corrections(text)


def word_count(text: str) -> int:
    """
    粗略统计英文词数。
    对字幕断句来说足够使用。
    """
    return len(re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", text))

def word_tokens(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", str(text).lower())


def ends_with_sentence_punctuation(text: str) -> bool:
    """
    判断是否以完整句标点结尾。
    英文字幕主要看 . ? !，同时兼容中文标点。
    """
    text = text.strip()
    return bool(re.search(r"[.!?。！？…]['\")\]]*$", text))


def starts_with_lowercase(text: str) -> bool:
    """
    如果下一行以小写字母开头，很可能是上一行的延续。

    例如：
    I want
    to start now.
    """
    text = text.strip()
    return bool(text) and text[0].islower()

def starts_with_continuation_fragment(text: str) -> bool:
    """
    判断下一行是否明显不是独立新句。

    Whisper / spaCy 偶尔会把一句话错误切成：
        America's past.
        divisions. The Smithsonian...

    这种下一行以小写词开头的片段，应在翻译前合回上一行，否则翻译模型
    会把 divisions 当成孤立名词，误译成“分部”。
    """
    text = normalize_space(text).lstrip(",.;:!?，。；：！？ ")
    if starts_with_lowercase(text):
        return True

    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text.lower())
    if not words:
        return False

    continuation_starters = {
        "a", "an", "the",
        "of", "to", "in", "on", "at", "by", "for", "from", "with", "without",
        "and", "or", "but", "so", "as", "if", "when", "while", "although",
        "because", "that", "which", "who", "where", "not", "then",
    }
    return words[0] in continuation_starters


def starts_with_capitalized_question(text: str) -> bool:
    text = normalize_space(text).lstrip(",.;:!?，。；：！？ ")
    return bool(
        re.match(
            r"^(?:What|Where|When|Why|Who|Whom|Whose|Which|How|"
            r"Did|Do|Does|Can|Could|Would|Will|Is|Are|Was|Were|Have|Has|Had)\b",
            text,
        )
    )

def join_for_merge(current: str, next_line: str) -> str:
    """
    合并两行。若下一行是延续片段，移除上一行误加的句号。
    """
    current = normalize_space(current)
    next_line = normalize_space(next_line)
    current_words = word_tokens(current)
    next_words = word_tokens(next_line)
    if current_words and next_words and current_words[-1] == next_words[0]:
        duplicate_match = re.match(
            r"^\s*[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?\s*([,;:，；：])?\s*(.*)$",
            next_line,
        )
        if duplicate_match:
            punct = duplicate_match.group(1) or ""
            rest = duplicate_match.group(2).strip()
            next_line = normalize_space(f"{punct} {rest}" if punct else rest)
    if starts_with_continuation_fragment(next_line):
        current = re.sub(r"[.!?。！？]+$", "", current)
        # 如果下一行以大写连接词开头（如 "And"），转为小写，避免中句大写
        m = re.match(r'^\s*([A-Z][a-z]+)\s', next_line)
        if m:
            w = m.group(1).lower()
            if w in {'and', 'or', 'but', 'so', 'for', 'nor', 'yet'}:
                next_line = next_line[:m.start(1)] + w + next_line[m.end(1):]
    merged = normalize_space(current + " " + next_line)
    merged = re.sub(r"\s+([,.;:!?，。；：！？])", r"\1", merged)
    merged = collapse_nonrepeatable_duplicates(merged)
    return apply_asr_phrase_corrections(merged)


# =========================
# 短句 / 碎片判断
# =========================

def is_hanging_fragment(text: str) -> bool:
    """
    判断当前行是否明显像一个未完成碎片。
    这些情况通常应该和下一行合并。
    """
    text = normalize_space(text)

    if not text:
        return False

    wc = word_count(text)

    # 1. 极短
    if len(text) < MIN_CHARS:
        return True

    # 2. 词数太少，并且没有完整句标点
    if wc < MIN_WORDS and not ends_with_sentence_punctuation(text):
        return True

    # 3. 常见功能词结尾：很明显后面还没说完
    hanging_endings = {
        "a", "an", "the",
        "to", "of", "for", "with", "without", "from", "in", "on", "at", "by",
        "and", "or", "but", "so", "because", "if", "when", "while", "although",
        "that", "which", "who", "whom", "whose",
        "is", "are", "was", "were", "be", "been", "being",
        "do", "does", "did",
        "have", "has", "had",
        "will", "would", "can", "could", "should", "may", "might", "must",
        "not", "n't",
        "i", "you", "he", "she", "it", "we", "they",
        "this", "these", "those",
        "my", "your", "his", "her", "our", "their",
    }

    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text.lower())
    if words:
        last_word = words[-1]
        if last_word in hanging_endings and not ends_with_sentence_punctuation(text):
            return True

    return False



# =========================
# 数字续接检测
# =========================

# 匹配 "1,500" 或 "1 000" 这类被 WhisperX 切断的数字
_NUMBER_FRAGMENT_END_RE = re.compile(r"(?:\d[,\s]*|\d+[,\s])$")
_NUMBER_FRAGMENT_START_RE = re.compile(r"^[,]?\d+")

def _ends_with_number_fragment(text: str) -> bool:
    """检测当前行是否以被切断的数字结尾。如 "almost 1" 中的 "1"、",000" 等。"""
    text = normalize_space(text)
    # 去除末尾标点后检查是否以数字结尾
    trimmed = re.sub(r"[.!?。！？…]+$", "", text).strip()
    return bool(re.search(r"(?:^|[\s,])\d+$", trimmed))

def _starts_with_number_fragment(text: str) -> bool:
    """检测下一行是否以数字碎片开头。如 ",500"、"000" 等。"""
    text = normalize_space(text).lstrip(",.;:!?，。；：！？ ")
    return bool(re.match(r"^[,]?\d+", text))

def _is_number_continuation(current: str, next_line: str) -> bool:
    """判断两行是否为同一个数字被切断的延续。"""
    return _ends_with_number_fragment(current) and _starts_with_number_fragment(next_line)

def should_merge_with_next(current: str, next_line: str) -> bool:
    """
    判断 current 是否应该和 next_line 合并。
    """
    current = normalize_space(current)
    next_line = normalize_space(next_line)

    if not current or not next_line:
        return False

    if ends_with_sentence_punctuation(current) and starts_with_capitalized_question(next_line):
        return False

    is_continuation = starts_with_continuation_fragment(next_line)
    merged = join_for_merge(current, next_line)
    raw_joined = normalize_space(current + " " + next_line)
    if apply_asr_phrase_corrections(raw_joined) != raw_joined:
        return True

    # 合并后太长，不合并
    # 后面 _3_2_split_meaning.py 和 _5_split_sub.py 会继续处理长句
    max_chars = MAX_CONTINUATION_MERGED_CHARS if is_continuation else MAX_MERGED_CHARS
    if len(merged) > max_chars:
        return False
    if is_continuation and word_count(merged) > MAX_CONTINUATION_MERGED_WORDS:
        return False

    # 数字被切断的延续：强制合并
    if _is_number_continuation(current, next_line):
        return True

    # 当前行明显是碎片
    if is_hanging_fragment(current):
        return True

    # 下一行以小写词或功能词开头，通常不是独立新句
    # 但如果当前行已是完整句（以 .!? 结尾）且下一行以大写字母开头，
    # 则是真正的新句，不应合并。例如 "cars. And Elon..." → 两句
    if is_continuation:
        if ends_with_sentence_punctuation(current) and next_line.strip() and next_line.strip()[0].isupper():
            return False
        return True

    # 当前行没有结束标点，下一行以小写开头，通常是同一句
    if not ends_with_sentence_punctuation(current) and starts_with_lowercase(next_line):
        return True

    # 当前行非常短，即使有标点，也可以和下一句合并
    # 例如：
    # Absolutely.
    # And I've said this to President Trump.
    if word_count(current) <= 2 and len(merged) <= MAX_MERGED_CHARS:
        return True

    return False


# =========================
# 核心合并逻辑
# =========================

def _line_timing_spans(lines: List[str], timed_words):
    if timed_words is None or not {"text", "start", "end"}.issubset(timed_words.columns):
        return [None] * len(lines)

    word_rows = timed_words.reset_index(drop=True)
    source_tokens = []
    source_row_indices = []
    for row_index, text in enumerate(word_rows["text"]):
        for token in word_tokens(text):
            source_tokens.append(token)
            source_row_indices.append(row_index)

    spans = []
    cursor = 0
    for line in lines:
        tokens = word_tokens(line)
        if not tokens:
            spans.append(None)
            continue

        match_start = None
        for candidate_start in range(cursor, len(source_tokens) - len(tokens) + 1):
            if source_tokens[candidate_start:candidate_start + len(tokens)] == tokens:
                match_start = candidate_start
                break
        if match_start is None:
            spans.append(None)
            continue

        match_end = match_start + len(tokens) - 1
        start_row = source_row_indices[match_start]
        end_row = source_row_indices[match_end]
        spans.append((float(word_rows.at[start_row, "start"]), float(word_rows.at[end_row, "end"])))
        cursor = match_end + 1
    return spans


def merge_lines(lines: List[str], timed_words=None) -> List[str]:
    """
    合并过短行。

    输入：
    按行切好的文本。

    输出：
    合并后的文本行。
    """
    cleaned = [normalize_space(line) for line in lines if normalize_space(line)]
    timing_spans = _line_timing_spans(cleaned, timed_words)
    merged_lines = []

    i = 0
    while i < len(cleaned):
        current = cleaned[i]
        merged_count = 1

        while (
            i + 1 < len(cleaned)
            and merged_count < MAX_MERGE_LINES
            and not (
                timing_spans[i] is not None
                and timing_spans[i + 1] is not None
                and timing_spans[i + 1][0] - timing_spans[i][1] >= PAUSE_PROTECTED_BOUNDARY_SECONDS
            )
            and should_merge_with_next(current, cleaned[i + 1])
        ):
            current = join_for_merge(current, cleaned[i + 1])
            i += 1
            merged_count += 1

            # 如果合并后已经是完整句，并且长度不算太短，就停止继续合并
            # 但像 Absolutely. 这种极短完整句，仍允许继续合并
            if ends_with_sentence_punctuation(current) and word_count(current) >= MIN_WORDS:
                if word_count(current) > 2:
                    break

        current = fix_broken_words(current)
        merged_lines.append(current)
        i += 1

    return merged_lines


# =========================
# 主函数
# =========================

def merge_short_segments_main():
    """
    主函数：

    1. 读取 _3_1_SPLIT_BY_NLP；
    2. 合并过短碎片；
    3. 修复少数断词；
    4. 覆盖写回 _3_1_SPLIT_BY_NLP。

    这个函数建议在 _3_1_split_nlp.py 中调用，
    放在 split_long_by_root_main(nlp) 后面。
    """
    with open(_3_1_SPLIT_BY_NLP, "r", encoding="utf-8") as f:
        original_lines = [line.strip() for line in f.readlines()]

    original_non_empty_count = len([line for line in original_lines if line.strip()])

    timed_words = None
    if os.path.exists(_2_CLEANED_CHUNKS):
        try:
            timed_words = pd.read_excel(_2_CLEANED_CHUNKS)
        except Exception as exc:
            console.print(f"[yellow]⚠️ Could not load ASR word timings for pause-aware merging: {exc}[/yellow]")

    merged_lines = merge_lines(original_lines, timed_words=timed_words)

    with open(_3_1_SPLIT_BY_NLP, "w", encoding="utf-8") as f:
        f.write("\n".join(merged_lines))

    table = Table(title="🔗 Merge short subtitle segments")
    table.add_column("Item", style="cyan")
    table.add_column("Count", style="magenta")

    table.add_row("Before", str(original_non_empty_count))
    table.add_row("After", str(len(merged_lines)))
    table.add_row("Merged", str(original_non_empty_count - len(merged_lines)))

    console.print(table)
    console.print("[green]✅ Short subtitle segments merged successfully.[/green]")


if __name__ == "__main__":
    merge_short_segments_main()
