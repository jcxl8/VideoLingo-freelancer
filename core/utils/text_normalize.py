import re


CJK_RE = r"\u4e00-\u9fff"
LATIN_RE = r"A-Za-z0-9"


def normalize_cjk_latin_spacing(text):
    """Add spaces between CJK text and Latin words/numbers in subtitle translations."""
    if text is None:
        return ""

    text = str(text)
    if not text:
        return ""

    text = re.sub(fr"([{CJK_RE}])([{LATIN_RE}])", r"\1 \2", text)
    text = re.sub(fr"([{LATIN_RE}])([{CJK_RE}])", r"\1 \2", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\s+([，。！？；：、])", r"\1", text)
    text = re.sub(r"([（【《“])\s+", r"\1", text)
    text = re.sub(r"\s+([）】》”])", r"\1", text)
    return text.strip()
