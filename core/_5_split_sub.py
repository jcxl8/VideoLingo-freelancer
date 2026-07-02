import concurrent.futures
import re
from typing import List, Tuple

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core._3_2_split_meaning import split_sentence
from core.prompts import get_align_prompt
from core.utils import *
from core.utils.models import *

console = Console()

LEADING_ACK_SOURCE_RE = re.compile(
    r"^\s*(?:Absolutely|Certainly|Sure|Of\s+course|Yes)\s*[.!?]\s+",
    re.I,
)
LEADING_ACK_TARGET_RE = re.compile(
    r"^\s*(?:当然|当然可以|可以|没问题|是的|对|行|好)[，。！？!?\s]*"
)


def _target_language_is_chinese() -> bool:
    target_language = str(load_key("target_language") or "").lower()
    return any(marker in target_language for marker in ("zh", "中文", "汉语", "簡體", "繁體"))


def _restore_leading_ack_translation(source: str, translation: str) -> str:
    source = str(source or "").strip()
    translation = str(translation or "").strip()
    if not translation or not LEADING_ACK_SOURCE_RE.match(source) or not _target_language_is_chinese():
        return translation
    if LEADING_ACK_TARGET_RE.match(translation):
        return translation
    return f"当然，{translation}"


def _restore_leading_acknowledgements(src_lines: List[str], tr_lines: List[str]) -> List[str]:
    restored = []
    restored_count = 0
    for src, tr in zip(src_lines, tr_lines):
        fixed = _restore_leading_ack_translation(src, tr)
        if fixed != str(tr or "").strip():
            restored_count += 1
        restored.append(fixed)
    if restored_count:
        console.print(f"[blue]ℹ️ Restored {restored_count} leading acknowledgement translation(s).[/blue]")
    return restored


def calc_len(text: str) -> float:
    text = str(text)

    def char_weight(char):
        code = ord(char)
        if 0x4E00 <= code <= 0x9FFF or 0x3040 <= code <= 0x30FF:
            return 1.75
        if 0xAC00 <= code <= 0xD7A3 or 0x1100 <= code <= 0x11FF:
            return 1.5
        if 0x0E00 <= code <= 0x0E7F:
            return 1
        if 0xFF01 <= code <= 0xFF5E:
            return 1.75
        return 1

    return sum(char_weight(char) for char in text)


def align_subs(src_sub: str, tr_sub: str, src_part: str) -> Tuple[List[str], List[str], str]:
    align_prompt = get_align_prompt(src_sub, tr_sub, src_part)

    def valid_align(response_data):
        if "align" not in response_data:
            return {"status": "error", "message": "Missing required key: `align`"}
        if len(response_data["align"]) < 2:
            return {"status": "error", "message": "Align does not contain more than 1 part as expected!"}
        return {"status": "success", "message": "Align completed"}

    parsed = ask_gpt(align_prompt, resp_type="json", valid_def=valid_align, log_title="align_subs")
    align_data = parsed["align"]
    src_parts = src_part.split("\n")
    tr_parts = [item[f"target_part_{i + 1}"].strip() for i, item in enumerate(align_data)]

    whisper_language = load_key("whisper.language")
    language = load_key("whisper.detected_language") if whisper_language == "auto" else whisper_language
    joiner = get_joiner(language)
    tr_remerged = joiner.join(tr_parts)

    table = Table(title="🔗 Aligned parts")
    table.add_column("Language", style="cyan")
    table.add_column("Parts", style="magenta")
    table.add_row("SRC_LANG", "\n".join(src_parts))
    table.add_row("TARGET_LANG", "\n".join(tr_parts))
    console.print(table)

    return src_parts, tr_parts, tr_remerged


def split_align_subs(src_lines: List[str], tr_lines: List[str]):
    subtitle_set = load_key("subtitle")
    max_sub_length = subtitle_set["max_length"]
    target_sub_multiplier = subtitle_set["target_multiplier"]
    remerged_tr_lines = tr_lines.copy()

    to_split = []
    for i, (src, tr) in enumerate(zip(src_lines, tr_lines)):
        src, tr = str(src), str(tr)
        if len(src) > max_sub_length or calc_len(tr) * target_sub_multiplier > max_sub_length:
            to_split.append(i)
            table = Table(title=f"📏 Line {i} needs to be split")
            table.add_column("Type", style="cyan")
            table.add_column("Content", style="magenta")
            table.add_row("Source Line", src)
            table.add_row("Target Line", tr)
            console.print(table)

    @except_handler("Error in split_align_subs")
    def process(i):
        split_src = split_sentence(src_lines[i], num_parts=2).strip()
        src_parts, tr_parts, tr_remerged = align_subs(src_lines[i], tr_lines[i], split_src)
        src_lines[i] = src_parts
        tr_lines[i] = tr_parts
        remerged_tr_lines[i] = tr_remerged

    with concurrent.futures.ThreadPoolExecutor(max_workers=load_key("max_workers")) as executor:
        executor.map(process, to_split)

    src_lines = [item for sublist in src_lines for item in (sublist if isinstance(sublist, list) else [sublist])]
    tr_lines = [item for sublist in tr_lines for item in (sublist if isinstance(sublist, list) else [sublist])]

    return src_lines, tr_lines, remerged_tr_lines


def split_for_sub_main():
    console.print("[bold green]🚀 Start splitting subtitles...[/bold green]")

    df = pd.read_excel(_4_2_TRANSLATION)
    src = df["Source"].tolist()
    trans = df["Translation"].tolist()

    subtitle_set = load_key("subtitle")
    max_sub_length = subtitle_set["max_length"]
    target_sub_multiplier = subtitle_set["target_multiplier"]

    for attempt in range(3):
        console.print(Panel(f"🔄 Split attempt {attempt + 1}", expand=False))
        split_src, split_trans, remerged = split_align_subs(src.copy(), trans)

        if all(len(item) <= max_sub_length for item in split_src) and all(
            calc_len(item) * target_sub_multiplier <= max_sub_length for item in split_trans
        ):
            break

        src, trans = split_src, split_trans

    if len(src) > len(remerged):
        remerged += [None] * (len(src) - len(remerged))
    elif len(remerged) > len(src):
        src += [None] * (len(remerged) - len(src))

    split_trans = _restore_leading_acknowledgements(split_src, split_trans)
    remerged = _restore_leading_acknowledgements(src, remerged)

    pd.DataFrame({"Source": split_src, "Translation": split_trans}).to_excel(_5_SPLIT_SUB, index=False)
    pd.DataFrame({"Source": src, "Translation": remerged}).to_excel(_5_REMERGED, index=False)


if __name__ == "__main__":
    split_for_sub_main()
