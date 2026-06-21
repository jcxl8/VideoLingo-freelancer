import re
from functools import lru_cache
from pathlib import Path


def ass_color(color):
    text = str(color).strip()
    if not text.startswith("&H"):
        return text
    hex_part = text[2:]
    if len(hex_part) == 6:
        return f"&H00{hex_part}"
    return text


def ass_escape(text):
    text = str(text or "").strip()
    text = text.replace("\\", r"\\")
    text = re.sub(r"[ \t]*\n[ \t]*", r"\\N", text)
    return text.replace("{", "(").replace("}", ")")


def parse_srt_timestamp(value):
    match = re.match(r"\s*(\d+):(\d+):(\d+),(\d+)\s*$", value or "")
    if not match:
        return None
    hours, minutes, seconds, millis = [int(part) for part in match.groups()]
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def ass_timestamp(seconds):
    seconds = max(0, float(seconds or 0))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    whole_seconds = int(seconds % 60)
    centiseconds = int(round((seconds - int(seconds)) * 100))
    if centiseconds >= 100:
        whole_seconds += 1
        centiseconds -= 100
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"


@lru_cache(maxsize=128)
def _read_srt_entries_cached(path, size, mtime_ns):
    content = Path(path).read_text(encoding="utf-8-sig").strip()
    if not content:
        return []
    entries = []
    for block in re.split(r"\n\s*\n", content):
        lines = [line.strip("\ufeff") for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        timestamp_index = next(
            (index for index, line in enumerate(lines) if "-->" in line), None
        )
        if timestamp_index is None:
            continue
        start_text, end_text = [
            part.strip() for part in lines[timestamp_index].split("-->", 1)
        ]
        start = parse_srt_timestamp(start_text)
        end = parse_srt_timestamp(end_text)
        if start is None or end is None:
            continue
        entries.append(
            {
                "start": start,
                "end": end,
                "text": "\n".join(lines[timestamp_index + 1 :]).strip(),
            }
        )
    return tuple((entry["start"], entry["end"], entry["text"]) for entry in entries)


def read_srt_entries(path):
    resolved = Path(path).expanduser().resolve()
    stat = resolved.stat()
    cached = _read_srt_entries_cached(str(resolved), stat.st_size, stat.st_mtime_ns)
    return [
        {"start": start, "end": end, "text": text}
        for start, end, text in cached
    ]
