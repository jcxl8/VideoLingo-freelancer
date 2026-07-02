import hashlib
import math
import os, subprocess, time, re
from dataclasses import dataclass
from core._1_ytdlp import find_video_files
import cv2
import numpy as np
import platform
from core.utils import *
from core.subtitle_layout import (
    Box as LayoutBox,
    PortraitMetrics,
    layout_bilingual,
    layout_hardsub,
)
from core.utils.process_errors import format_process_error
from core.job_manifest import record_subtitle_merge
from core.subtitle_formats import (
    ass_color as _ass_color,
    ass_escape as _ass_escape,
    ass_timestamp as _ass_timestamp,
    parse_srt_timestamp as _parse_srt_timestamp,
    read_srt_entries as _read_srt_entries,
)

SRC_FONT_SIZE = 44
TRANS_FONT_SIZE = 48
FONT_NAME = 'Arial'
TRANS_FONT_NAME = 'Arial'

# Linux need to install google noto fonts: apt-get install fonts-noto
if platform.system() == 'Linux':
    FONT_NAME = 'NotoSansCJK-Regular'
    TRANS_FONT_NAME = 'NotoSansCJK-Regular'
# Mac OS has different font names
elif platform.system() == 'Darwin':
    FONT_NAME = 'Arial Unicode MS'
    TRANS_FONT_NAME = 'Arial Unicode MS'

SRC_FONT_COLOR = '&HFFFFFF'
SRC_OUTLINE_COLOR = '&H000000'
SRC_OUTLINE_WIDTH = 2
SRC_SHADOW_COLOR = '&H80000000'
TRANS_FONT_COLOR = '&H00FFFF'
TRANS_OUTLINE_COLOR = '&H000000'
TRANS_OUTLINE_WIDTH = 1
TRANS_BACK_COLOR = '&H66000000'

SUBTITLE_LAYOUT_AUTO = "auto"
SUBTITLE_LAYOUT_LANDSCAPE = "landscape"
SUBTITLE_LAYOUT_PORTRAIT = "portrait_9_16"
PORTRAIT_RATIO_THRESHOLD = 1.6
PORTRAIT_SUBTITLE_BOTTOM_RATIO = 0.78
PORTRAIT_SAFE_SIDE_MARGIN = 20
HARDSUB_AVOID_GAP = 8
WATERMARK_TRANSLATION_GAP = 10

HARDSUB_STRATEGY_AUTO = "auto"
HARDSUB_STRATEGY_NONE = "none"
HARDSUB_STRATEGY_SOURCE = "source_hardsub"
SUBTITLE_LAYOUT_PROFILE_DEFAULT = "default"
SUBTITLE_LAYOUT_PROFILES = {
    SUBTITLE_LAYOUT_PROFILE_DEFAULT: {
        "label": "Default",
        "hardsub_translation_base_offset": 0,
        "watermark_base_offset": 0,
    },
}
HARDSUB_SCAN_FRAME_COUNT = 24
HARDSUB_MIN_DETECTION_RATIO = 0.25
HARDSUB_AUTO_MIN_CONFIDENCE = 0.35
HARDSUB_AUTO_MIN_WIDTH_RATIO = 0.25
HARDSUB_AUTO_MAX_CENTER_OFFSET = 0.22
HARDSUB_AUTO_MAX_HEIGHT_RATIO = 0.18
HARDSUB_AUTO_MAX_BOTTOM_RATIO = 0.95
SUBTITLE_STYLE_VERSION = 21
PORTRAIT_SRC_MIN_SINGLE_LINE_FONT_SIZE = 26
PORTRAIT_SRC_MIN_SINGLE_LINE_SCALE_X = 96
PORTRAIT_SRC_WRAP_FONT_RATIO = 0.90

LANDSCAPE_BLOCK_GAP = 6
LANDSCAPE_WATERMARK_SUBTITLE_GAP = 15
LANDSCAPE_WATERMARK_DEFAULT_OFFSET = -100


def landscape_watermark_effective_gap(offset=None):
    if offset is None:
        offset = _safe_int_key(
            "landscape_watermark_offset",
            LANDSCAPE_WATERMARK_DEFAULT_OFFSET,
        )
    adjustment = int(offset) - LANDSCAPE_WATERMARK_DEFAULT_OFFSET
    return LANDSCAPE_WATERMARK_SUBTITLE_GAP + adjustment


# Watermark
WATERMARK_TEXT = 'AI 词级视频译制'
WATERMARK_OPACITY = 0.30

if platform.system() == 'Linux':
    WATERMARK_FONT_FILE = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
elif platform.system() == 'Darwin':
    WATERMARK_FONT_FILE = '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
else:
    WATERMARK_FONT_FILE = 'C:/Windows/Fonts/msyh.ttc'
def _load_watermark_font_size():
    try:
        return int(load_key("watermark_font_size"))
    except Exception:
        return SRC_FONT_SIZE


OUTPUT_DIR = "output"
OUTPUT_VIDEO = f"{OUTPUT_DIR}/output_sub.mp4"
SRC_SRT = f"{OUTPUT_DIR}/src.srt"
TRANS_SRT = f"{OUTPUT_DIR}/trans.srt"

def sanitize_filename_part(text):
    text = str(text).strip()
    text = text.replace("简体中文", "zh-CN").replace("繁體中文", "zh-TW")
    text = text.replace("中文", "zh").replace("英语", "en").replace("英文", "en")
    text = re.sub(r"[^\w\-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def get_translation_model_name():
    """Return the name of the translation model used for subtitles, sanitized for filenames."""
    try:
        model = load_key("translator_api.model")
        if model and str(model).strip():
            return sanitize_filename_part(str(model).strip())
    except KeyError:
        pass
    try:
        model = load_key("api.model")
        if model:
            return sanitize_filename_part(str(model).strip())
    except KeyError:
        pass
    return "default"

def get_language_pair_name():
    whisper_language = load_key("whisper.language")
    source_language = load_key("whisper.detected_language") if whisper_language == "auto" else whisper_language
    target_language = load_key("target_language")
    model_name = get_translation_model_name()
    return f"{sanitize_filename_part(source_language)}_to_{sanitize_filename_part(target_language)}_{model_name}"

def get_video_base_name(video_file):
    return sanitize_filename_part(os.path.splitext(os.path.basename(video_file))[0])

def get_subtitle_mode_suffix(subtitle_mode):
    return {
        "source_only": "src",
        "translation_only": "trans",
        "bilingual_src_top": "src_trans",
        "bilingual_trans_top": "trans_src",
        "single_bilingual_trans_top": "trans_src",
    }.get(subtitle_mode, "sub")

def get_available_output_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    version = 2
    while True:
        candidate = f"{base}_v{version}{ext}"
        if not os.path.exists(candidate):
            return candidate
        version += 1

def get_default_output_video_path(video_file=None, prefix="", subtitle_mode=None, avoid_overwrite=False):
    if video_file is None:
        video_file = find_video_files()
    mode_suffix = f"_{get_subtitle_mode_suffix(subtitle_mode)}" if subtitle_mode else ""
    file_name = f"{prefix}{get_video_base_name(video_file)}_{get_language_pair_name()}{mode_suffix}_sub.mp4"
    output_path = os.path.join(OUTPUT_DIR, file_name)
    return get_available_output_path(output_path) if avoid_overwrite else output_path

def get_subtitle_base_name(video_file=None):
    if video_file is None:
        video_file = find_video_files()
    return f"{get_video_base_name(video_file)}_{get_language_pair_name()}"

def get_default_subtitle_paths(video_file=None, output_dir=OUTPUT_DIR):
    subtitle_base = get_subtitle_base_name(video_file)
    return {
        "src": os.path.join(output_dir, f"{subtitle_base}_src.srt"),
        "trans": os.path.join(output_dir, f"{subtitle_base}_trans.srt"),
        "src_trans": os.path.join(output_dir, f"{subtitle_base}_src_trans.srt"),
        "trans_src": os.path.join(output_dir, f"{subtitle_base}_trans_src.srt"),
    }
    
def check_gpu_available():
    try:
        result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
        return 'h264_nvenc' in result.stdout
    except:
        return False

def _safe_load_key(key, default=None):
    try:
        return load_key(key)
    except Exception:
        return default

def _safe_int_key(key, default=0):
    try:
        return int(load_key(key))
    except Exception:
        return default


@dataclass(frozen=True)
class PortraitStyleConfig:
    source_font_size: int = 45
    translation_font_size: int = 45
    hardsub_translation_font_size: int = 45
    bilingual_offset: int = 0
    hardsub_translation_offset: int = 0
    watermark_font_size: int = 27
    watermark_offset: int = 0


def _portrait_int_setting(new_key, legacy_key, default):
    value = _safe_load_key(new_key, None)
    if value is None and legacy_key:
        value = _safe_load_key(legacy_key, default)
    if value is None:
        value = default
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _portrait_style_config():
    return PortraitStyleConfig(
        source_font_size=_portrait_int_setting("portrait_source_font_size", None, 45),
        translation_font_size=_portrait_int_setting("portrait_translation_font_size", None, 45),
        hardsub_translation_font_size=_portrait_int_setting(
            "portrait_hardsub_translation_font_size", None, 45
        ),
        bilingual_offset=_portrait_int_setting(
            "portrait_bilingual_offset", "bilingual_translation_offset", 0
        ),
        hardsub_translation_offset=_portrait_int_setting(
            "portrait_hardsub_translation_offset", "hardsub_translation_offset", 0
        ),
        watermark_font_size=_portrait_int_setting(
            "portrait_watermark_font_size", "watermark_font_size", 27
        ),
        watermark_offset=_portrait_int_setting(
            "portrait_watermark_offset", "watermark_offset", 0
        ),
    )


def _scale_portrait_size(reference_size, target_width, minimum=24, maximum=160):
    scaled = round(int(reference_size) * max(1, int(target_width)) / 576)
    return max(minimum, min(maximum, scaled))

def _clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))

def _is_bilingual_mode(subtitle_mode):
    return subtitle_mode in ("bilingual_src_top", "bilingual_trans_top", "single_bilingual_trans_top")

def _hardsub_strategy():
    strategy = str(_safe_load_key("subtitle_hardsub_strategy", HARDSUB_STRATEGY_AUTO) or HARDSUB_STRATEGY_AUTO)
    if strategy in (HARDSUB_STRATEGY_AUTO, HARDSUB_STRATEGY_NONE, HARDSUB_STRATEGY_SOURCE):
        return strategy
    return HARDSUB_STRATEGY_AUTO

def _subtitle_layout_profile():
    profile = str(_safe_load_key("subtitle_layout_profile", SUBTITLE_LAYOUT_PROFILE_DEFAULT) or SUBTITLE_LAYOUT_PROFILE_DEFAULT)
    return profile if profile in SUBTITLE_LAYOUT_PROFILES else SUBTITLE_LAYOUT_PROFILE_DEFAULT

def _subtitle_layout_profile_config():
    return SUBTITLE_LAYOUT_PROFILES.get(_subtitle_layout_profile(), SUBTITLE_LAYOUT_PROFILES[SUBTITLE_LAYOUT_PROFILE_DEFAULT])

def _effective_hardsub_translation_offset(layout=SUBTITLE_LAYOUT_LANDSCAPE):
    profile_base = int(_subtitle_layout_profile_config().get("hardsub_translation_base_offset", 0))
    if layout == SUBTITLE_LAYOUT_PORTRAIT:
        return profile_base + _portrait_style_config().hardsub_translation_offset
    return profile_base + _safe_int_key("landscape_hardsub_translation_offset", 0)

def _effective_watermark_offset(layout=SUBTITLE_LAYOUT_LANDSCAPE):
    profile_base = int(_subtitle_layout_profile_config().get("watermark_base_offset", 0))
    if layout == SUBTITLE_LAYOUT_PORTRAIT:
        return profile_base + _portrait_style_config().watermark_offset
    return profile_base + _safe_int_key(
        "landscape_watermark_offset",
        LANDSCAPE_WATERMARK_DEFAULT_OFFSET,
    )

def _portrait_hardsub_placement():
    """Return the hard-sub translation placement preference.

    Values: "auto" (smart), "above" (always above), "below" (always below).
    """
    return str(_safe_load_key("portrait_hardsub_placement", "auto") or "auto")


def _is_portrait_video(target_width, target_height):
    return target_height > 0 and target_width > 0 and (target_height / target_width) >= PORTRAIT_RATIO_THRESHOLD

def _subtitle_layout_for_video(target_width, target_height):
    layout = str(_safe_load_key("subtitle_layout", SUBTITLE_LAYOUT_AUTO) or SUBTITLE_LAYOUT_AUTO)
    if layout == SUBTITLE_LAYOUT_AUTO:
        return SUBTITLE_LAYOUT_PORTRAIT if _is_portrait_video(target_width, target_height) else SUBTITLE_LAYOUT_LANDSCAPE
    if layout in (SUBTITLE_LAYOUT_LANDSCAPE, SUBTITLE_LAYOUT_PORTRAIT):
        return layout
    return SUBTITLE_LAYOUT_PORTRAIT if _is_portrait_video(target_width, target_height) else SUBTITLE_LAYOUT_LANDSCAPE

def _portrait_subtitle_margin_v(target_height):
    return max(20, int(round(target_height * (1 - PORTRAIT_SUBTITLE_BOTTOM_RATIO))))

def _portrait_safe_side_margin(target_width):
    return max(PORTRAIT_SAFE_SIDE_MARGIN, int(round(target_width * 20 / 576)))

def _portrait_font_sizes(target_width):
    style = _portrait_style_config()
    return (
        _scale_portrait_size(style.source_font_size, target_width, maximum=118),
        _scale_portrait_size(style.translation_font_size, target_width, maximum=118),
    )


def _portrait_hardsub_translation_font_size(target_width):
    return _scale_portrait_size(
        _portrait_style_config().hardsub_translation_font_size,
        target_width,
        maximum=118,
    )

def _watermark_font_size_for_video(target_width=None):
    if not target_width:
        return _portrait_style_config().watermark_font_size
    return _scale_portrait_size(
        _portrait_style_config().watermark_font_size,
        target_width,
        minimum=12,
        maximum=96,
    )

def _portrait_line_heights(src_size, trans_size):
    return int(round(src_size * 1.28)), int(round(trans_size * 1.24))

def _portrait_block_gap(target_height):
    return max(6, int(round(target_height * 0.006)))


def _landscape_font_sizes(target_width, target_height):
    scale = max(1, int(target_height or 1080)) / 1080.0
    src_reference = _safe_int_key("landscape_source_font_size", 50)
    trans_reference = _safe_int_key("landscape_translation_font_size", 55)
    src_size = max(12, min(220, int(round(src_reference * scale))))
    trans_size = max(12, min(220, int(round(trans_reference * scale))))
    return src_size, trans_size

def _landscape_safe_margin_h(target_width):
    return max(40, int(round(int(target_width or 1920) * 0.05)))

def _landscape_bottom_margin_v(target_height):
    return max(16, int(round(int(target_height or 1080) * 0.018)))

def _landscape_block_gap(target_height):
    return max(4, int(round(int(target_height or 1080) * 0.005)))

def _landscape_line_heights(src_size, trans_size):
    return int(round(src_size * 1.28)), int(round(trans_size * 1.24))


def _landscape_bilingual_top_y(
    src_srt,
    trans_srt,
    target_width,
    target_height,
):
    src_entries = _read_srt_entries(src_srt)
    trans_entries = _read_srt_entries(trans_srt)
    count = min(len(src_entries), len(trans_entries))
    if count == 0:
        return None

    margin_h = _landscape_safe_margin_h(target_width)
    src_size, trans_size = _landscape_font_sizes(target_width, target_height)
    src_line_height, trans_line_height = _landscape_line_heights(
        src_size,
        trans_size,
    )
    block_gap = _landscape_block_gap(target_height)
    tallest_block = 0
    for index in range(count):
        _, src_line_count = _wrap_source_subtitle_for_ass(
            src_entries[index]["text"],
            target_width,
            src_size,
            margin_h,
        )
        trans_line_count = len(
            _wrap_subtitle_lines(
                trans_entries[index]["text"],
                target_width,
                trans_size,
                margin_h,
            )
        )
        tallest_block = max(
            tallest_block,
            src_line_count * src_line_height
            + block_gap
            + trans_line_count * trans_line_height,
        )

    block_base_margin = _clamp(
        _landscape_bottom_margin_v(target_height)
        + _safe_int_key("landscape_bilingual_translation_offset", 0),
        0,
        target_height,
    )
    return _clamp(
        target_height - block_base_margin - tallest_block,
        0,
        target_height,
    )


def _landscape_bilingual_entry_top_ys(
    src_srt,
    trans_srt,
    target_width,
    target_height,
):
    src_entries = _read_srt_entries(src_srt)
    trans_entries = _read_srt_entries(trans_srt)
    count = min(len(src_entries), len(trans_entries))
    margin_h = _landscape_safe_margin_h(target_width)
    src_size, trans_size = _landscape_font_sizes(target_width, target_height)
    src_line_height, trans_line_height = _landscape_line_heights(src_size, trans_size)
    block_gap = _landscape_block_gap(target_height)
    block_base_margin = _clamp(
        _landscape_bottom_margin_v(target_height)
        + _safe_int_key("landscape_bilingual_translation_offset", 0),
        0,
        target_height,
    )
    top_ys = []
    for index in range(count):
        _, src_line_count = _wrap_source_subtitle_for_ass(
            src_entries[index]["text"], target_width, src_size, margin_h
        )
        trans_line_count = len(
            _wrap_subtitle_lines(
                trans_entries[index]["text"], target_width, trans_size, margin_h
            )
        )
        block_height = (
            src_line_count * src_line_height
            + block_gap
            + trans_line_count * trans_line_height
        )
        top_ys.append(
            _clamp(target_height - block_base_margin - block_height, 0, target_height)
        )
    return top_ys


def _landscape_watermark_bottom_y(subtitle_top_y, offset=None):
    if offset is None:
        offset = _effective_watermark_offset(SUBTITLE_LAYOUT_LANDSCAPE)
    gap = landscape_watermark_effective_gap(offset)
    return int(subtitle_top_y) - gap

def _landscape_subtitle_style(target_width, target_height):
    """Return (src_size, trans_size, margin_v, margin_h) for landscape non-bilingual modes."""
    tw = int(target_width or 1920)
    th = int(target_height or 1080)
    margin_h = _landscape_safe_margin_h(tw)
    margin_v = _landscape_bottom_margin_v(th)
    src_size, trans_size = _landscape_font_sizes(tw, th)
    return src_size, trans_size, margin_v, margin_h

def _subtitle_line_scan_region(target_width, target_height):
    x1 = int(round(target_width * 0.08))
    x2 = int(round(target_width * 0.92))
    y1 = int(round(target_height * 0.45))
    y2 = int(round(target_height * 0.92))
    return x1, y1, x2, y2

def _estimate_text_width_px(text, font_size):
    width = 0.0
    for char in str(text or ""):
        codepoint = ord(char)
        if char.isspace():
            width += font_size * 0.26
        elif codepoint > 127:
            width += font_size * 0.92
        elif char in ".,:;!?'`|ilI[](){}":
            width += font_size * 0.28
        elif char in "fjt":
            width += font_size * 0.36
        elif char in "mwMW@#%&":
            width += font_size * 0.72
        elif char.isupper():
            width += font_size * 0.58
        else:
            width += font_size * 0.46
    return width

CJK_QUOTED_TERM_RE = re.compile(r"《[^》]{1,40}》")
LATIN_PROPER_TERM_RE = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)?(?:\s+[A-Z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)?)+\b")
CJK_PREDICATE_AFTER_TERM_RE = re.compile(r"^(?:这位|这名|这个|该|当|做|担任|成为|饰演|扮演|出演|作为|给|为|和|与)")
CJK_GOOD_BREAK_AFTER_RE = re.compile(
    r"(?:老师|教师|导演|演员|角色|人物|医生|律师|记者|主持人|公司|团队|作品|电影|剧集|节目|"
    r"语言|俄语|韩语|英语|中文|外星语|技能|能力|场景|问题|事情|时候|地方|国家|城市|学校|医院)$"
)
CJK_BAD_BREAK_AROUND_RE = re.compile(r"^(?:语|老师|教师|导演|演员|格|伯|文|星)")

def _protected_visual_spans(text):
    text = str(text or "")
    spans = [(match.start(), match.end()) for match in CJK_QUOTED_TERM_RE.finditer(text)]
    spans.extend(_cjk_middle_dot_name_spans(text))
    spans.extend((match.start(), match.end()) for match in LATIN_PROPER_TERM_RE.finditer(text))
    return sorted(spans)

def _cjk_middle_dot_name_spans(text):
    text = str(text or "")
    spans = []
    for match in re.finditer("·", text):
        dot_index = match.start()
        left_start = dot_index
        while left_start > 0 and re.match(r"[\u3400-\u9fff]", text[left_start - 1]):
            left_start -= 1
        right_end = dot_index + 1
        while right_end < len(text) and re.match(r"[\u3400-\u9fff]", text[right_end]):
            right_end += 1

        left_run = text[left_start:dot_index]
        right_run = text[dot_index + 1:right_end]
        if len(left_run) < 2 or len(right_run) < 2:
            continue

        name_left = left_run[-4:]
        for prefix in ("还有", "我和", "以及", "和", "与", "跟", "由", "在", "为", "给"):
            if name_left.startswith(prefix) and len(name_left) - len(prefix) >= 2:
                name_left = name_left[len(prefix):]
                break
        if len(name_left) < 2:
            continue

        right_len = min(len(right_run), 5)
        name_right = right_run[:right_len]
        start = dot_index - len(name_left)
        end = dot_index + 1 + len(name_right)
        spans.append((start, end))
    return spans

def _is_inside_protected_visual_span(spans, split_index):
    return any(start < split_index < end for start, end in spans)

def _adjust_protected_split_index(text, line_start, split_index, max_width, font_size, spans):
    for span_start, span_end in spans:
        if not (span_start < split_index < span_end):
            continue

        candidates = []
        if span_end > line_start and _estimate_text_width_px(text[line_start:span_end], font_size) <= max_width:
            candidates.append(span_end)
        if span_start > line_start and _estimate_text_width_px(text[line_start:span_start], font_size) <= max_width:
            candidates.append(span_start)
        if not candidates:
            return split_index

        return min(
            candidates,
            key=lambda candidate: abs(
                _estimate_text_width_px(text[line_start:candidate], font_size)
                - _estimate_text_width_px(text[candidate:], font_size)
            ),
        )
    return split_index

def _preferred_protected_term_split(token, max_width, font_size, spans):
    for span_start, span_end in spans:
        left = token[:span_end].strip()
        right = token[span_end:].strip()
        if not left or not right:
            continue
        if not CJK_PREDICATE_AFTER_TERM_RE.match(right):
            continue
        if _estimate_text_width_px(left, font_size) <= max_width and _estimate_text_width_px(right, font_size) <= max_width:
            return [left, right]
    return None

def _is_mostly_cjk_text(text):
    compact = re.sub(r"\s+", "", str(text or ""))
    if not compact:
        return False
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", compact))
    return cjk_count / len(compact) >= 0.65

def _semantic_cjk_break_score(left, right, max_width, font_size, spans):
    left = str(left or "").strip()
    right = str(right or "").strip()
    if not left or not right:
        return None
    left_width = _estimate_text_width_px(left, font_size)
    right_width = _estimate_text_width_px(right, font_size)
    if left_width > max_width or right_width > max_width:
        return None

    split_index = len(left)
    if _is_inside_protected_visual_span(spans, split_index):
        return None
    if CJK_BAD_BREAK_AROUND_RE.match(right):
        return None

    balance = abs(left_width - right_width)
    score = balance
    if CJK_GOOD_BREAK_AFTER_RE.search(left):
        score -= max_width * 0.55
    if any(span_end == split_index for _, span_end in spans):
        score -= max_width * 0.9
    if re.search(r"[，,；;：:。！？!?]$", left):
        score -= max_width * 0.45
    if right.startswith(("这位", "这名", "这个", "该", "很棒的", "超棒的", "还有", "和", "与", "并且", "而且")):
        score -= max_width * 0.25
    if len(right) <= 2:
        score += max_width * 1.2
    return score

def _preferred_cjk_semantic_split(token, max_width, font_size, spans):
    if not _is_mostly_cjk_text(token):
        return None
    best = None
    for split_index in range(1, len(token)):
        left = token[:split_index]
        right = token[split_index:]
        score = _semantic_cjk_break_score(left, right, max_width, font_size, spans)
        if score is None:
            continue
        if best is None or score < best[0]:
            best = (score, left.strip(), right.strip())
    if best:
        return [best[1], best[2]]
    return None

def _split_long_token(token, max_width, font_size):
    token = str(token or "")
    protected_spans = _protected_visual_spans(token)
    preferred_split = _preferred_protected_term_split(token, max_width, font_size, protected_spans)
    if preferred_split:
        return preferred_split
    preferred_split = _preferred_cjk_semantic_split(token, max_width, font_size, protected_spans)
    if preferred_split:
        return preferred_split

    lines = []
    line_start = 0
    index = 0
    while index < len(token):
        candidate = token[line_start:index + 1]
        if index > line_start and _estimate_text_width_px(candidate, font_size) > max_width:
            split_index = _adjust_protected_split_index(
                token,
                line_start,
                index,
                max_width,
                font_size,
                protected_spans,
            )
            if split_index <= line_start or split_index > len(token):
                split_index = index
            lines.append(token[line_start:split_index])
            line_start = split_index
            continue
        index += 1
    if line_start < len(token):
        lines.append(token[line_start:])
    if len(lines) >= 2 and len(lines[-1].strip()) <= 2:
        combined = lines[-2] + lines[-1]
        combined_spans = _protected_visual_spans(combined)
        best_split = None
        best_score = None
        for split_index in range(1, len(combined)):
            if _is_inside_protected_visual_span(combined_spans, split_index):
                continue
            left = combined[:split_index]
            right = combined[split_index:]
            left_width = _estimate_text_width_px(left, font_size)
            right_width = _estimate_text_width_px(right, font_size)
            if left_width > max_width or right_width > max_width:
                continue
            if len(right.strip()) <= 2:
                continue
            score = abs(left_width - right_width)
            if best_score is None or score < best_score:
                best_score = score
                best_split = (left, right)
        if best_split:
            lines[-2], lines[-1] = best_split
    return lines

def _word_count(text):
    return len(re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", str(text or "")))

def _last_words(text, count):
    words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", str(text or "").lower())
    return " ".join(words[-count:]) if len(words) >= count else " ".join(words)

def _first_words(text, count):
    words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", str(text or "").lower())
    return " ".join(words[:count])

def _is_orphan_subtitle_line(text, font_size):
    stripped = str(text or "").strip()
    if not stripped:
        return True
    return _word_count(stripped) <= 1 or _estimate_text_width_px(stripped, font_size) < font_size * 5.5

def _subtitle_break_penalty(left, right, font_size):
    left = str(left or "").strip()
    right = str(right or "").strip()
    left_words = _word_count(left)
    right_words = _word_count(right)
    penalty = 0.0

    if left_words <= 1 or right_words <= 1:
        penalty += 8000
    if _is_orphan_subtitle_line(right, font_size):
        penalty += 6000

    first_right = _first_words(right, 1)
    last_left = _last_words(left, 1)
    left2 = _last_words(left, 2)
    left3 = _last_words(left, 3)
    right2 = _first_words(right, 2)
    right4 = _first_words(right, 4)
    bridge2 = f"{last_left} {first_right}".strip()
    bridge3 = f"{left2} {first_right}".strip()
    bridge4 = f"{last_left} {right2}".strip()
    right3 = _first_words(right, 3)

    protected_phrases = {
        "up and down", "jumping up", "down at", "tour the", "the lab",
        "meet the", "of the", "in the", "on the", "at the",
        "to the", "for the", "with the", "from the",
        "i mean",
    }
    if bridge2 in protected_phrases or bridge3 in protected_phrases or bridge4 in protected_phrases:
        penalty += 5200
    if right3 == "up and down":
        penalty += 7000
    if right4 == "jumping up and down":
        penalty += 7000
    if bridge2 == "invited to":
        penalty += 3000

    # Avoid ending a line with a preposition/determiner unless it materially
    # improves the layout. This is softer than orphan-word penalties because
    # user-preferred breaks like "invited to / tour..." can still win.
    if last_left in {"a", "an", "the", "of", "in", "on", "at", "by", "for", "from", "with"}:
        penalty += 1200
    if first_right in {"and", "or", "but", "the", "a", "an", "of", "in", "on", "by", "for", "with"}:
        penalty += 1000

    # Keep common verb phrases together when possible.
    if bridge3 in {"were invited to", "was invited to", "be invited to"}:
        penalty -= 4500
    if left3 in {"were invited to", "was invited to", "be invited to"}:
        penalty -= 6500
    if left.lower().endswith("up and down"):
        penalty -= 7200

    # Prefer a readable second line rather than a tiny tail.
    right_width = _estimate_text_width_px(right, font_size)
    if right_words >= 4:
        penalty -= min(500, right_width * 0.05)
    return penalty

def _wrap_subtitle_lines_balanced(text, target_width, font_size, margin_h, max_lines=2):
    tokens = [token for token in text.split(" ") if token]
    if len(tokens) <= 1 or max_lines != 2:
        return None

    max_width = max(1, target_width - margin_h * 2)
    candidates = []
    for split_index in range(1, len(tokens)):
        left = " ".join(tokens[:split_index])
        right = " ".join(tokens[split_index:])
        left_width = _estimate_text_width_px(left, font_size)
        right_width = _estimate_text_width_px(right, font_size)
        if left_width > max_width or right_width > max_width:
            continue

        balance = abs(left_width - right_width)
        max_line_width = max(left_width, right_width)
        fill_ratio = max_line_width / max_width
        penalty = _subtitle_break_penalty(left, right, font_size)

        # Prefer balanced lines, but do not force both lines to be equal at the
        # expense of phrase boundaries or orphan words.
        score = balance + penalty + max(0.0, fill_ratio - 0.92) * 1200
        candidates.append((score, split_index, left, right))

    if not candidates:
        return None
    _, _, left, right = min(candidates, key=lambda item: item[0])
    return [left, right]

def _avoid_final_single_word_line(lines, font_size, max_width):
    lines = [str(line or "").strip() for line in lines if str(line or "").strip()]
    if len(lines) < 2 or _word_count(lines[-1]) != 1:
        return lines

    previous_words = lines[-2].split()
    if len(previous_words) <= 1:
        return lines

    borrowed = previous_words[-1]
    new_previous = " ".join(previous_words[:-1]).strip()
    new_last = f"{borrowed} {lines[-1]}".strip()
    if (
        new_previous
        and _estimate_text_width_px(new_previous, font_size) <= max_width
        and _estimate_text_width_px(new_last, font_size) <= max_width
    ):
        lines[-2] = new_previous
        lines[-1] = new_last
    return lines

def _semantic_source_clause_lines_for_ass(text, font_size, max_width):
    text = re.sub(r"\s+", " ", str(text or "").strip())
    match = re.match(r"^(.+?,)\s+(and\b.+?)\s+(because\b.+)$", text, re.I)
    if not match:
        return []
    lines = [match.group(1).strip(), match.group(2).strip(), match.group(3).strip()]
    if any(_word_count(line) < 3 for line in lines):
        return []
    if all(_estimate_text_width_px(line, font_size) <= max_width for line in lines):
        return lines
    return []

def _wrap_subtitle_lines(text, target_width, font_size, margin_h, max_lines=2):
    text = re.sub(r"\s+", " ", str(text or "").strip())
    if not text:
        return [""]

    max_width = max(1, target_width - margin_h * 2)
    if _estimate_text_width_px(text, font_size) <= max_width:
        return [text]

    balanced_lines = _wrap_subtitle_lines_balanced(text, target_width, font_size, margin_h, max_lines=max_lines)
    if balanced_lines:
        return _avoid_final_single_word_line(balanced_lines, font_size, max_width)

    tokens = text.split(" ")
    lines = []
    current = ""
    for token in tokens:
        if not token:
            continue
        candidate = f"{current} {token}".strip() if current else token
        if not current:
            if _estimate_text_width_px(candidate, font_size) <= max_width:
                current = candidate
            else:
                split_tokens = _split_long_token(candidate, max_width, font_size)
                lines.extend(split_tokens[:-1])
                current = split_tokens[-1] if split_tokens else ""
        elif _estimate_text_width_px(candidate, font_size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            if _estimate_text_width_px(token, font_size) <= max_width:
                current = token
            else:
                split_tokens = _split_long_token(token, max_width, font_size)
                lines.extend(split_tokens[:-1])
                current = split_tokens[-1] if split_tokens else ""
    if current:
        lines.append(current)

    if len(lines) <= max_lines:
        return _avoid_final_single_word_line(lines, font_size, max_width)

    overflow_line = " ".join(lines[max_lines - 1:])
    if _estimate_text_width_px(overflow_line, font_size) <= max_width:
        return _avoid_final_single_word_line(lines[:max_lines - 1] + [overflow_line], font_size, max_width)

    # Do not rejoin CJK or other long text into an over-wide final ASS line.
    # Keeping an extra line is much less damaging than rendering text outside
    # the video frame during burn-in.
    return _avoid_final_single_word_line(lines, font_size, max_width)

def _ass_text_from_lines(lines):
    escaped = []
    for line in lines:
        escaped.append(
            str(line or "")
            .strip()
            .replace("\\", r"\\")
            .replace("{", "(")
            .replace("}", ")")
        )
    return r"\N".join(escaped)

def _ass_text_with_inline_style(lines, font_size=None, scale_x=None):
    text = _ass_text_from_lines(lines)
    tags = []
    if font_size:
        tags.append(f"\\fs{font_size}")
    if scale_x and int(scale_x) != 100:
        tags.append(f"\\fscx{int(scale_x)}")
    if tags:
        return "{" + "".join(tags) + "}" + text
    return text

def _wrap_source_subtitle_for_ass(text, target_width, font_size, margin_h, max_lines=2):
    text = re.sub(r"\s+", " ", str(text or "").strip())
    if not text:
        return "", 1

    max_width = max(1, target_width - margin_h * 2)
    estimated_width = _estimate_text_width_px(text, font_size)
    if estimated_width <= max_width:
        return _ass_text_with_inline_style([text]), 1

    full_size_lines = _wrap_subtitle_lines(text, target_width, font_size, margin_h, max_lines=max_lines)
    if (
        len(full_size_lines) <= max_lines
        and all(_estimate_text_width_px(line, font_size) <= max_width for line in full_size_lines)
    ):
        return _ass_text_with_inline_style(full_size_lines), len(full_size_lines)

    scale_x = int(max_width / estimated_width * 100)
    if _word_count(text) <= 8 and scale_x >= PORTRAIT_SRC_MIN_SINGLE_LINE_SCALE_X:
        return _ass_text_with_inline_style([text], scale_x=scale_x), 1

    wrap_font_size = min(
        font_size,
        max(PORTRAIT_SRC_MIN_SINGLE_LINE_FONT_SIZE, int(round(font_size * PORTRAIT_SRC_WRAP_FONT_RATIO))),
    )
    semantic_lines = _semantic_source_clause_lines_for_ass(text, wrap_font_size, max_width)
    if semantic_lines:
        override_size = wrap_font_size if wrap_font_size != font_size else None
        return _ass_text_with_inline_style(semantic_lines, font_size=override_size), len(semantic_lines)

    lines = _wrap_subtitle_lines(text, target_width, wrap_font_size, margin_h, max_lines=max_lines)
    override_size = wrap_font_size if wrap_font_size != font_size else None
    return _ass_text_with_inline_style(lines, font_size=override_size), len(lines)

def _sample_video_frames(video_file, max_frames=HARDSUB_SCAN_FRAME_COUNT):
    capture = cv2.VideoCapture(video_file)
    if not capture.isOpened():
        return []
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    duration = frame_count / fps if frame_count > 0 and fps > 0 else 0
    if frame_count > 0:
        indices = np.linspace(max(0, frame_count * 0.12), max(0, frame_count * 0.88), max_frames).astype(int)
    elif duration > 0:
        indices = np.linspace(duration * 0.12, duration * 0.88, max_frames)
    else:
        indices = np.arange(max_frames)

    frames = []
    for index in indices:
        if frame_count > 0:
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        elif fps > 0:
            capture.set(cv2.CAP_PROP_POS_MSEC, float(index) * 1000)
        ok, frame = capture.read()
        if ok and frame is not None:
            frames.append(frame)
    capture.release()
    return frames

def _detect_hardsub_box_in_frame(frame):
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = _subtitle_line_scan_region(width, height)
    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:
        return None

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    bright = (gray > 178) & (hsv[:, :, 1] < 90)
    mask = bright.astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 2))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1)), iterations=1)

    row_counts = mask.sum(axis=1) / 255
    threshold = max(10, int(round((x2 - x1) * 0.018)))
    active_rows = np.where(row_counts >= threshold)[0]
    if len(active_rows) == 0:
        return None

    groups = []
    start = prev = int(active_rows[0])
    for row in active_rows[1:]:
        row = int(row)
        if row - prev <= 3:
            prev = row
        else:
            groups.append((start, prev))
            start = prev = row
    groups.append((start, prev))

    candidates = []
    roi_width = x2 - x1
    line_merge_gap = max(10, int(round(height * 0.028)))
    for top, bottom in groups:
        group_height = bottom - top + 1
        if group_height < 5 or group_height > height * 0.13:
            continue
        rows = mask[max(0, top - 1):min(mask.shape[0], bottom + 2), :]
        cols = np.where(rows.sum(axis=0) > 0)[0]
        if len(cols) == 0:
            continue
        left = int(cols[0])
        right = int(cols[-1])
        width_ratio = (right - left + 1) / max(1, roi_width)
        center_ratio = (left + right) / 2 / max(1, roi_width)
        if width_ratio < 0.12 or width_ratio > 0.88 or center_ratio < 0.18 or center_ratio > 0.82:
            continue
        score = float(row_counts[top:bottom + 1].sum()) * (1 + width_ratio)
        candidates.append({
            "top": y1 + top,
            "bottom": y1 + bottom,
            "left": x1 + left,
            "right": x1 + right,
            "score": score,
        })

    if not candidates:
        return None

    candidates.sort(key=lambda item: item["top"])
    blocks = []
    for candidate in candidates:
        if not blocks:
            blocks.append(dict(candidate))
            continue
        current = blocks[-1]
        vertical_gap = candidate["top"] - current["bottom"]
        horizontal_overlap = min(current["right"], candidate["right"]) - max(current["left"], candidate["left"])
        min_width = max(1, min(current["right"] - current["left"], candidate["right"] - candidate["left"]))
        centered_together = abs(((current["left"] + current["right"]) / 2) - ((candidate["left"] + candidate["right"]) / 2)) <= roi_width * 0.22
        if vertical_gap <= line_merge_gap and (horizontal_overlap / min_width >= 0.15 or centered_together):
            current["top"] = min(current["top"], candidate["top"])
            current["bottom"] = max(current["bottom"], candidate["bottom"])
            current["left"] = min(current["left"], candidate["left"])
            current["right"] = max(current["right"], candidate["right"])
            current["score"] += candidate["score"]
            current["lines"] = current.get("lines", 1) + 1
        else:
            blocks.append(dict(candidate))

    for block in blocks:
        block.setdefault("lines", 1)
    return max(blocks, key=lambda item: (item["bottom"], item["lines"], item["score"]))

_HARDSUB_DETECTION_CACHE = {}


def clear_hardsub_detection_cache():
    _HARDSUB_DETECTION_CACHE.clear()


def _hardsub_cache_key(video_file, target_width, target_height):
    try:
        stat = os.stat(video_file)
        fingerprint = (os.path.abspath(video_file), stat.st_size, stat.st_mtime_ns)
    except OSError:
        fingerprint = (str(video_file), None, None)
    return fingerprint + (target_width, target_height, SUBTITLE_STYLE_VERSION)


def detect_existing_source_hardsub(video_file, target_width=None, target_height=None):
    cache_key = _hardsub_cache_key(video_file, target_width, target_height)
    if cache_key in _HARDSUB_DETECTION_CACHE:
        cached = _HARDSUB_DETECTION_CACHE[cache_key]
        return dict(cached) if cached else None
    frames = _sample_video_frames(video_file)
    boxes = []
    for frame in frames:
        box = _detect_hardsub_box_in_frame(frame)
        if box:
            boxes.append(box)
    if not boxes:
        _HARDSUB_DETECTION_CACHE[cache_key] = None
        return None

    confidence = len(boxes) / max(1, len(frames))
    if confidence < HARDSUB_MIN_DETECTION_RATIO:
        _HARDSUB_DETECTION_CACHE[cache_key] = None
        return None
    frame_height, frame_width = frames[0].shape[:2]

    cluster_gap = max(24, int(round(frame_height * 0.09)))
    sorted_boxes = sorted(
        boxes,
        key=lambda item: (int(item["top"]) + int(item.get("bottom", item["top"]))) / 2,
    )
    clusters = []
    for box in sorted_boxes:
        center = (int(box["top"]) + int(box.get("bottom", box["top"]))) / 2
        if not clusters:
            clusters.append({"boxes": [box], "centers": [center]})
            continue
        current_center = float(np.median(clusters[-1]["centers"]))
        if abs(center - current_center) <= cluster_gap:
            clusters[-1]["boxes"].append(box)
            clusters[-1]["centers"].append(center)
        else:
            clusters.append({"boxes": [box], "centers": [center]})

    def cluster_score(cluster):
        cluster_boxes = cluster["boxes"]
        return (
            len(cluster_boxes),
            sum(float(box.get("score", 0)) for box in cluster_boxes),
            max(int(box.get("lines", 1)) for box in cluster_boxes),
        )

    main_boxes = max(clusters, key=cluster_score)["boxes"]
    top = int(round(float(np.percentile([box["top"] for box in main_boxes], 15))))
    bottom = int(round(float(np.percentile([box["bottom"] for box in main_boxes], 85))))
    left = int(round(float(np.median([box["left"] for box in main_boxes]))))
    right = int(round(float(np.median([box["right"] for box in main_boxes]))))
    widest_line_count = max(box.get("lines", 1) for box in main_boxes)
    result = {
        "top": top,
        "bottom": bottom,
        "left": left,
        "right": right,
        "confidence": round(confidence, 2),
        "samples": len(main_boxes),
        "lines": widest_line_count,
        "center_ratio": round(((left + right) / 2) / max(1, frame_width), 2),
        "width_ratio": round((right - left) / max(1, frame_width), 2),
        "height_ratio": round((bottom - top) / max(1, frame_height), 2),
        "bottom_ratio": round(bottom / max(1, frame_height), 2),
    }
    _HARDSUB_DETECTION_CACHE[cache_key] = dict(result)
    return result

def _is_reliable_auto_hardsub_detection(detected):
    if not detected:
        return False
    center_offset = abs(float(detected.get("center_ratio", 0.5)) - 0.5)
    return (
        float(detected.get("confidence", 0)) >= HARDSUB_AUTO_MIN_CONFIDENCE
        and float(detected.get("width_ratio", 0)) >= HARDSUB_AUTO_MIN_WIDTH_RATIO
        and center_offset <= HARDSUB_AUTO_MAX_CENTER_OFFSET
        and float(detected.get("height_ratio", 1)) <= HARDSUB_AUTO_MAX_HEIGHT_RATIO
        and float(detected.get("bottom_ratio", 1)) <= HARDSUB_AUTO_MAX_BOTTOM_RATIO
    )

def _format_hardsub_detection(detected):
    if not detected:
        return "none"
    return (
        f"y={detected.get('top')}-{detected.get('bottom')}, "
        f"confidence={detected.get('confidence')}, "
        f"center={detected.get('center_ratio')}, "
        f"width={detected.get('width_ratio')}, "
        f"height={detected.get('height_ratio')}, "
        f"bottom={detected.get('bottom_ratio')}"
    )

def _fallback_source_hardsub_box(target_width, target_height):
    src_size, trans_size = _portrait_font_sizes(target_width)
    src_line_height, _ = _portrait_line_heights(src_size, trans_size)
    base_margin_v = _portrait_subtitle_margin_v(target_height)
    bottom = target_height - base_margin_v
    top = bottom - src_line_height
    return {
        "top": top,
        "bottom": bottom,
        "left": _portrait_safe_side_margin(target_width),
        "right": target_width - _portrait_safe_side_margin(target_width),
        "confidence": 0,
        "samples": 0,
    }

def _text_width_units(text):
    units = 0.0
    for char in str(text or ""):
        if char == "\n":
            continue
        units += 1.0 if ord(char) > 127 else 0.55
    return units

def _estimate_ass_lines(text, target_width, font_size, margin_h):
    explicit_lines = [line for line in str(text or "").splitlines() if line.strip()]
    if len(explicit_lines) > 1:
        return min(3, len(explicit_lines))
    usable_width = max(1, target_width - margin_h * 2)
    max_units = max(6, usable_width / max(1, font_size * 0.62))
    return max(1, min(3, int(math.ceil(_text_width_units(text) / max_units))))


def _portrait_metrics(target_width, target_height):
    src_size, trans_size = _portrait_font_sizes(target_width)
    return PortraitMetrics(
        width=target_width,
        height=target_height,
        source_font_size=src_size,
        translation_font_size=trans_size,
        hardsub_translation_font_size=_portrait_hardsub_translation_font_size(target_width),
        watermark_font_size=_watermark_font_size_for_video(target_width),
        side_margin=_portrait_safe_side_margin(target_width),
        safe_vertical_margin=max(10, int(round(target_height * 10 / 1024))),
        subtitle_gap=max(HARDSUB_AVOID_GAP, int(round(target_height * 8 / 1024))),
        watermark_gap=max(WATERMARK_TRANSLATION_GAP, int(round(target_width * 10 / 576))),
    )


def _max_source_line_count(src_srt, target_width, font_size, margin_h):
    entries = _read_srt_entries(src_srt) if src_srt else []
    counts = [
        _wrap_source_subtitle_for_ass(
            entry["text"], target_width, font_size, margin_h
        )[1]
        for entry in entries
    ]
    return max(counts, default=1)


def _max_translation_line_count(trans_srt, target_width, font_size, margin_h):
    entries = _read_srt_entries(trans_srt) if trans_srt else []
    counts = [
        len(_wrap_subtitle_lines(entry["text"], target_width, font_size, margin_h))
        for entry in entries
    ]
    return max(counts, default=1)


def _portrait_layout_for_subtitles(
    src_srt,
    trans_srt,
    subtitle_mode,
    target_width,
    target_height,
    source_hardsub_box=None,
    source_line_count=None,
    translation_line_count=None,
):
    metrics = _portrait_metrics(target_width, target_height)
    style = _portrait_style_config()
    if source_hardsub_box:
        trans_lines = translation_line_count or _max_translation_line_count(
            trans_srt,
            target_width,
            metrics.hardsub_translation_font_size,
            metrics.side_margin,
        )
        hard_box = LayoutBox(
            int(source_hardsub_box.get("left", metrics.side_margin)),
            int(source_hardsub_box["top"]),
            int(source_hardsub_box.get("right", target_width - metrics.side_margin)),
            int(source_hardsub_box.get("bottom", source_hardsub_box["top"])),
        )
        return layout_hardsub(
            metrics,
            hard_box,
            trans_lines,
            _effective_hardsub_translation_offset(SUBTITLE_LAYOUT_PORTRAIT),
            _effective_watermark_offset(SUBTITLE_LAYOUT_PORTRAIT),
            prefer=_portrait_hardsub_placement(),
        )

    src_lines = source_line_count or _max_source_line_count(
        src_srt,
        target_width,
        metrics.source_font_size,
        metrics.side_margin,
    )
    trans_lines = translation_line_count or _max_translation_line_count(
        trans_srt,
        target_width,
        metrics.translation_font_size,
        metrics.side_margin,
    )
    return layout_bilingual(
        metrics,
        src_lines,
        trans_lines,
        subtitle_mode,
        style.bilingual_offset,
        _effective_watermark_offset(SUBTITLE_LAYOUT_PORTRAIT),
    )

def _create_portrait_bilingual_ass(
    src_srt,
    trans_srt,
    subtitle_mode,
    target_width,
    target_height,
    portrait_layout=None,
):
    src_entries = _read_srt_entries(src_srt)
    trans_entries = _read_srt_entries(trans_srt)
    count = min(len(src_entries), len(trans_entries))
    if count == 0:
        raise RuntimeError("No subtitle entries found for portrait bilingual ASS generation.")

    os.makedirs(os.path.join(OUTPUT_DIR, "cache"), exist_ok=True)
    style = _portrait_style_config()
    cache_key = hashlib.sha1(
        f"{SUBTITLE_STYLE_VERSION}|{src_srt}|{trans_srt}|{subtitle_mode}|{target_width}|{target_height}|{style}|{os.path.getmtime(src_srt)}|{os.path.getmtime(trans_srt)}".encode("utf-8")
    ).hexdigest()[:16]
    ass_path = os.path.join(OUTPUT_DIR, "cache", f"portrait_bilingual_{cache_key}.ass")

    margin_h = _portrait_safe_side_margin(target_width)
    src_size, trans_size = _portrait_font_sizes(target_width)
    trans_top = subtitle_mode != "bilingual_src_top"
    entry_specs = []
    for index in range(count):
        src = src_entries[index]
        trans = trans_entries[index]
        src_text, source_line_count = _wrap_source_subtitle_for_ass(
            src["text"], target_width, src_size, margin_h
        )
        trans_lines = _wrap_subtitle_lines(
            trans["text"], target_width, trans_size, margin_h
        )
        entry_layout = _portrait_layout_for_subtitles(
            src_srt,
            trans_srt,
            subtitle_mode,
            target_width,
            target_height,
            source_line_count=source_line_count,
            translation_line_count=len(trans_lines),
        )
        entry_specs.append(
            (
                src,
                trans,
                src_text,
                _ass_text_from_lines(trans_lines),
                max(0, target_height - entry_layout.source.bottom),
                max(0, target_height - entry_layout.translation.bottom),
            )
        )
    base_margin_v = min(entry_specs[0][4], entry_specs[0][5])

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {target_width}
PlayResY: {target_height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TransTop,{TRANS_FONT_NAME},{trans_size},{_ass_color(TRANS_FONT_COLOR)},&H000000FF,{_ass_color(TRANS_OUTLINE_COLOR)},{_ass_color(TRANS_BACK_COLOR)},-1,0,0,0,100,100,0,0,4,{TRANS_OUTLINE_WIDTH},0,2,{margin_h},{margin_h},{base_margin_v},1
Style: TransBottom,{TRANS_FONT_NAME},{trans_size},{_ass_color(TRANS_FONT_COLOR)},&H000000FF,{_ass_color(TRANS_OUTLINE_COLOR)},{_ass_color(TRANS_BACK_COLOR)},-1,0,0,0,100,100,0,0,4,{TRANS_OUTLINE_WIDTH},0,2,{margin_h},{margin_h},{base_margin_v},1
Style: SrcTop,{FONT_NAME},{src_size},{_ass_color(SRC_FONT_COLOR)},&H000000FF,{_ass_color(SRC_OUTLINE_COLOR)},&H00000000,-1,0,0,0,100,100,0,0,1,{SRC_OUTLINE_WIDTH},0,2,{margin_h},{margin_h},{base_margin_v},1
Style: SrcBottom,{FONT_NAME},{src_size},{_ass_color(SRC_FONT_COLOR)},&H000000FF,{_ass_color(SRC_OUTLINE_COLOR)},&H00000000,-1,0,0,0,100,100,0,0,1,{SRC_OUTLINE_WIDTH},0,2,{margin_h},{margin_h},{base_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for src, trans, src_text, trans_text, src_margin, trans_margin in entry_specs:
        start = min(src["start"], trans["start"])
        end = max(src["end"], trans["end"])
        start_text = _ass_timestamp(start)
        end_text = _ass_timestamp(end)

        if trans_top:
            lines.append(f"Dialogue: 1,{start_text},{end_text},TransTop,,{margin_h},{margin_h},{trans_margin},,{trans_text}\n")
            lines.append(f"Dialogue: 0,{start_text},{end_text},SrcBottom,,{margin_h},{margin_h},{src_margin},,{src_text}\n")
        else:
            lines.append(f"Dialogue: 1,{start_text},{end_text},SrcTop,,{margin_h},{margin_h},{src_margin},,{src_text}\n")
            lines.append(f"Dialogue: 0,{start_text},{end_text},TransBottom,,{margin_h},{margin_h},{trans_margin},,{trans_text}\n")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return ass_path

def _hardsub_translation_placement(source_hardsub_box, target_height):
    if not source_hardsub_box or not target_height:
        return "below"
    remaining_below = target_height - int(
        source_hardsub_box.get("bottom", source_hardsub_box["top"])
    )
    return "below" if remaining_below >= target_height * 0.16 else "above"

def _hardsub_translation_geometry(source_hardsub_box, target_width, target_height):
    metrics = _portrait_metrics(target_width, target_height)
    hard_box = LayoutBox(
        int(source_hardsub_box.get("left", metrics.side_margin)),
        int(source_hardsub_box["top"]),
        int(source_hardsub_box.get("right", target_width - metrics.side_margin)),
        int(source_hardsub_box.get("bottom", source_hardsub_box["top"])),
    )
    portrait_layout = layout_hardsub(
        metrics,
        hard_box,
        2,
        _effective_hardsub_translation_offset(SUBTITLE_LAYOUT_PORTRAIT),
        _effective_watermark_offset(SUBTITLE_LAYOUT_PORTRAIT),
        prefer=_portrait_hardsub_placement(),
    )
    margin_v = (
        portrait_layout.translation.top
        if portrait_layout.translation_alignment == 8
        else target_height - portrait_layout.translation.bottom
    )
    return {
        "placement": portrait_layout.placement,
        "alignment": portrait_layout.translation_alignment,
        "margin_v": margin_v,
        "subtitle_y": portrait_layout.translation.top,
        "translation_bottom_y": portrait_layout.translation.bottom,
        "watermark_y": portrait_layout.watermark.top,
        "watermark_bottom_y": portrait_layout.watermark.bottom,
    }

def _create_translation_avoiding_hardsub_ass(
    trans_srt,
    target_width,
    target_height,
    source_hardsub_box,
    portrait_layout=None,
):
    trans_entries = _read_srt_entries(trans_srt)
    if not trans_entries:
        raise RuntimeError("No translated subtitle entries found for hard-subtitle overlay generation.")

    os.makedirs(os.path.join(OUTPUT_DIR, "cache"), exist_ok=True)
    hardsub_top = int(source_hardsub_box["top"])
    hardsub_bottom = int(source_hardsub_box.get("bottom", hardsub_top))
    style = _portrait_style_config()
    trans_size = _portrait_hardsub_translation_font_size(target_width)
    margin_h = _portrait_safe_side_margin(target_width)
    entry_specs = []
    geometry_names = {}
    base_name_counts = {}
    for entry in trans_entries:
        trans_lines = _wrap_subtitle_lines(
            entry["text"], target_width, trans_size, margin_h
        )
        entry_layout = _portrait_layout_for_subtitles(
            None,
            trans_srt,
            "translation_only",
            target_width,
            target_height,
            source_hardsub_box,
            translation_line_count=len(trans_lines),
        )
        margin_v = (
            entry_layout.translation.top
            if entry_layout.translation_alignment == 8
            else target_height - entry_layout.translation.bottom
        )
        geometry_key = (
            entry_layout.placement,
            entry_layout.translation_alignment,
            margin_v,
        )
        if geometry_key not in geometry_names:
            base_name = (
                "TransAboveHardSub"
                if entry_layout.placement == "above"
                else "TransBelowHardSub"
            )
            suffix = base_name_counts.get(base_name, 0)
            geometry_names[geometry_key] = base_name if suffix == 0 else f"{base_name}_{suffix + 1}"
            base_name_counts[base_name] = suffix + 1
        entry_specs.append(
            (
                entry,
                _ass_text_from_lines(trans_lines),
                geometry_names[geometry_key],
                entry_layout.translation_alignment,
                margin_v,
            )
        )
    placements = "+".join(sorted({key[0] for key in geometry_names}))
    cache_key = hashlib.sha1(
        f"{SUBTITLE_STYLE_VERSION}|{trans_srt}|source_hardsub|{_subtitle_layout_profile()}|{placements}|{target_width}|{target_height}|{hardsub_top}|{hardsub_bottom}|{style}|{os.path.getmtime(trans_srt)}".encode("utf-8")
    ).hexdigest()[:16]
    ass_path = os.path.join(OUTPUT_DIR, "cache", f"translation_avoiding_hardsub_{cache_key}.ass")

    style_lines = []
    for (placement, alignment, margin_v), style_name in geometry_names.items():
        style_lines.append(
            f"Style: {style_name},{TRANS_FONT_NAME},{trans_size},{_ass_color(TRANS_FONT_COLOR)},"
            f"&H000000FF,{_ass_color(TRANS_OUTLINE_COLOR)},{_ass_color(TRANS_BACK_COLOR)},"
            f"-1,0,0,0,100,100,0,0,4,{TRANS_OUTLINE_WIDTH},0,{alignment},"
            f"{margin_h},{margin_h},{margin_v},1"
        )

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {target_width}
PlayResY: {target_height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{chr(10).join(style_lines)}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for entry, trans_text, style_name, alignment, margin_v in entry_specs:
        lines.append(
            f"Dialogue: 0,{_ass_timestamp(entry['start'])},{_ass_timestamp(entry['end'])},"
            f"{style_name},,{margin_h},{margin_h},{margin_v},,{trans_text}\n"
        )

    with open(ass_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return ass_path

def _create_translation_above_hardsub_ass(trans_srt, target_width, target_height, source_hardsub_box):
    return _create_translation_avoiding_hardsub_ass(trans_srt, target_width, target_height, source_hardsub_box)

def _source_hardsub_box_for_video(video_file, subtitle_mode, target_width, target_height, layout):
    if not video_file or subtitle_mode == "source_only":
        return None
    strategy = _hardsub_strategy()
    if strategy == HARDSUB_STRATEGY_NONE:
        return None
    if layout != SUBTITLE_LAYOUT_PORTRAIT:
        return None

    if strategy == HARDSUB_STRATEGY_SOURCE:
        detected = detect_existing_source_hardsub(video_file, target_width, target_height)
        if detected:
            rprint(f"[blue]ℹ️ Detected existing source hard subtitles ({_format_hardsub_detection(detected)}).[/blue]")
            return detected
        fallback = _fallback_source_hardsub_box(target_width, target_height)
        rprint("[yellow]⚠️ Source hard-subtitle mode is forced, but no existing subtitle was detected. Using the default source-subtitle track position.[/yellow]")
        return fallback

    if strategy == HARDSUB_STRATEGY_AUTO:
        detected = detect_existing_source_hardsub(video_file, target_width, target_height)
        if _is_reliable_auto_hardsub_detection(detected):
            rprint(f"[blue]ℹ️ Auto-detected existing source hard subtitles ({_format_hardsub_detection(detected)}). Only translated subtitles will be burned above them.[/blue]")
            return detected
        if detected:
            rprint(f"[yellow]⚠️ Ignored uncertain hard-subtitle detection in auto mode ({_format_hardsub_detection(detected)}). Keeping the selected subtitle mode.[/yellow]")
        return None
    return None

def _subtitle_filter(
    srt_path,
    font_size,
    font_name,
    primary_color,
    outline_color,
    outline_width,
    alignment=2,
    margin_v=20,
    border_style=4,
    back_color=None,
    margin_l=None,
    margin_r=None,
):
    srt_path = _stage_subtitle_filter_input(srt_path)
    style = (
        f"FontSize={font_size},FontName={font_name},"
        f"PrimaryColour={primary_color},OutlineColour={outline_color},OutlineWidth={outline_width},"
        f"Alignment={alignment},MarginV={margin_v},BorderStyle={border_style}"
    )
    if margin_l is not None:
        style += f",MarginL={margin_l}"
    if margin_r is not None:
        style += f",MarginR={margin_r}"
    if back_color:
        style += f",BackColour={back_color}"
    return f"subtitles={srt_path}:force_style='{style}'"


def _stage_subtitle_filter_input(srt_path):
    """Copy SRT input to an FFmpeg-filter-safe cache path.

    History project names may contain apostrophes or other filtergraph syntax.
    Passing those paths directly to ``subtitles=`` makes FFmpeg parse the path
    as part of the filter expression even though subprocess itself is shell-safe.
    """
    source_path = os.fspath(srt_path)
    with open(source_path, "rb") as source:
        content = source.read()
    digest = hashlib.sha1(content).hexdigest()[:16]
    cache_dir = os.path.join(OUTPUT_DIR, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    staged_path = os.path.join(cache_dir, f"subtitle_input_{digest}.srt")
    if not os.path.exists(staged_path):
        temporary_path = f"{staged_path}.{os.getpid()}.tmp"
        with open(temporary_path, "wb") as target:
            target.write(content)
        os.replace(temporary_path, staged_path)
    return staged_path

def _bilingual_margin_v(value, target_height=None):
    max_value = target_height if target_height else 10000
    return _clamp(int(value) + _safe_int_key("bilingual_translation_offset", 0), 0, max_value)

def _create_landscape_bilingual_ass(src_srt, trans_srt, subtitle_mode, target_width, target_height):
    src_entries = _read_srt_entries(src_srt)
    trans_entries = _read_srt_entries(trans_srt)
    count = min(len(src_entries), len(trans_entries))
    if count == 0:
        raise RuntimeError("No subtitle entries found for landscape bilingual ASS generation.")

    os.makedirs(os.path.join(OUTPUT_DIR, "cache"), exist_ok=True)
    bilingual_subtitle_offset = _safe_int_key("landscape_bilingual_translation_offset", 0)
    cache_key = hashlib.sha1(
        f"{SUBTITLE_STYLE_VERSION}|{src_srt}|{trans_srt}|{subtitle_mode}|{target_width}|{target_height}|{bilingual_subtitle_offset}|{os.path.getmtime(src_srt)}|{os.path.getmtime(trans_srt)}".encode("utf-8")
    ).hexdigest()[:16]
    ass_path = os.path.join(OUTPUT_DIR, "cache", f"landscape_bilingual_{cache_key}.ass")

    margin_h = _landscape_safe_margin_h(target_width)
    base_margin_v = _landscape_bottom_margin_v(target_height)
    src_size, trans_size = _landscape_font_sizes(target_width, target_height)
    src_line_height, trans_line_height = _landscape_line_heights(src_size, trans_size)
    block_gap = _landscape_block_gap(target_height)
    trans_top = subtitle_mode in ("bilingual_trans_top", "single_bilingual_trans_top")

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {target_width}
PlayResY: {target_height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TransTop,{TRANS_FONT_NAME},{trans_size},{_ass_color(TRANS_FONT_COLOR)},&H000000FF,{_ass_color(TRANS_OUTLINE_COLOR)},{_ass_color(TRANS_BACK_COLOR)},-1,0,0,0,100,100,0,0,4,{TRANS_OUTLINE_WIDTH},0,2,{margin_h},{margin_h},{base_margin_v},1
Style: TransBottom,{TRANS_FONT_NAME},{trans_size},{_ass_color(TRANS_FONT_COLOR)},&H000000FF,{_ass_color(TRANS_OUTLINE_COLOR)},{_ass_color(TRANS_BACK_COLOR)},-1,0,0,0,100,100,0,0,4,{TRANS_OUTLINE_WIDTH},0,2,{margin_h},{margin_h},{base_margin_v},1
Style: SrcTop,{FONT_NAME},{src_size},{_ass_color(SRC_FONT_COLOR)},&H000000FF,{_ass_color(SRC_OUTLINE_COLOR)},&H00000000,-1,0,0,0,100,100,0,0,1,{SRC_OUTLINE_WIDTH},0,2,{margin_h},{margin_h},{base_margin_v},1
Style: SrcBottom,{FONT_NAME},{src_size},{_ass_color(SRC_FONT_COLOR)},&H000000FF,{_ass_color(SRC_OUTLINE_COLOR)},&H00000000,-1,0,0,0,100,100,0,0,1,{SRC_OUTLINE_WIDTH},0,2,{margin_h},{margin_h},{base_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for index in range(count):
        src = src_entries[index]
        trans = trans_entries[index]
        start = min(src["start"], trans["start"])
        end = max(src["end"], trans["end"])
        start_text = _ass_timestamp(start)
        end_text = _ass_timestamp(end)
        src_text, src_line_count = _wrap_source_subtitle_for_ass(src["text"], target_width, src_size, margin_h)
        trans_lines = _wrap_subtitle_lines(trans["text"], target_width, trans_size, margin_h)
        trans_text = _ass_text_from_lines(trans_lines)

        block_base_margin = _clamp(base_margin_v + bilingual_subtitle_offset, 0, target_height)
        if trans_top:
            src_margin = block_base_margin
            trans_margin = _clamp(
                block_base_margin + src_line_count * src_line_height + block_gap,
                0,
                target_height,
            )
            lines.append(f"Dialogue: 1,{start_text},{end_text},TransTop,,{margin_h},{margin_h},{trans_margin},,{trans_text}\n")
            lines.append(f"Dialogue: 0,{start_text},{end_text},SrcBottom,,{margin_h},{margin_h},{src_margin},,{src_text}\n")
        else:
            trans_margin = block_base_margin
            src_margin = _clamp(trans_margin + len(trans_lines) * trans_line_height + block_gap, 0, target_height)
            lines.append(f"Dialogue: 1,{start_text},{end_text},SrcTop,,{margin_h},{margin_h},{src_margin},,{src_text}\n")
            lines.append(f"Dialogue: 0,{start_text},{end_text},TransBottom,,{margin_h},{margin_h},{trans_margin},,{trans_text}\n")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return ass_path


def _create_landscape_single_ass(srt_path, subtitle_mode, target_width, target_height):
    entries = _read_srt_entries(srt_path)
    if not entries:
        raise RuntimeError("No subtitle entries found for landscape single-subtitle ASS generation.")
    if subtitle_mode not in ("source_only", "translation_only"):
        raise ValueError(f"Unsupported landscape single-subtitle mode: {subtitle_mode}")

    os.makedirs(os.path.join(OUTPUT_DIR, "cache"), exist_ok=True)
    margin_h = _landscape_safe_margin_h(target_width)
    margin_v = _landscape_bottom_margin_v(target_height)
    src_size, trans_size = _landscape_font_sizes(target_width, target_height)
    is_translation = subtitle_mode == "translation_only"
    font_name = TRANS_FONT_NAME if is_translation else FONT_NAME
    font_size = trans_size if is_translation else src_size
    primary_color = _ass_color(TRANS_FONT_COLOR if is_translation else SRC_FONT_COLOR)
    outline_color = _ass_color(TRANS_OUTLINE_COLOR if is_translation else SRC_OUTLINE_COLOR)
    outline_width = TRANS_OUTLINE_WIDTH if is_translation else SRC_OUTLINE_WIDTH
    border_style = 4 if is_translation else 1
    back_color = _ass_color(TRANS_BACK_COLOR) if is_translation else "&H00000000"
    cache_key = hashlib.sha1(
        (
            f"{SUBTITLE_STYLE_VERSION}|{srt_path}|{subtitle_mode}|{target_width}|{target_height}|"
            f"{font_size}|{margin_h}|{margin_v}|{os.path.getmtime(srt_path)}"
        ).encode("utf-8")
    ).hexdigest()[:16]
    ass_path = os.path.join(OUTPUT_DIR, "cache", f"landscape_single_{cache_key}.ass")

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {target_width}
PlayResY: {target_height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Single,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},{back_color},-1,0,0,0,100,100,0,0,{border_style},{outline_width},0,2,{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for entry in entries:
        if is_translation:
            text = _ass_text_from_lines(
                _wrap_subtitle_lines(entry["text"], target_width, font_size, margin_h)
            )
        else:
            text, _ = _wrap_source_subtitle_for_ass(
                entry["text"], target_width, font_size, margin_h
            )
        lines.append(
            f"Dialogue: 0,{_ass_timestamp(entry['start'])},{_ass_timestamp(entry['end'])},"
            f"Single,,{margin_h},{margin_h},{margin_v},,{text}\n"
        )
    with open(ass_path, "w", encoding="utf-8") as file:
        file.writelines(lines)
    return ass_path


def _create_landscape_watermark_ass(src_srt, trans_srt, target_width, target_height):
    """Create per-event watermark positions exactly above each bilingual block."""
    src_entries = _read_srt_entries(src_srt)
    trans_entries = _read_srt_entries(trans_srt)
    count = min(len(src_entries), len(trans_entries))
    if count == 0:
        raise RuntimeError("No subtitle entries found for landscape watermark generation.")

    os.makedirs(os.path.join(OUTPUT_DIR, "cache"), exist_ok=True)
    watermark_offset = _effective_watermark_offset(SUBTITLE_LAYOUT_LANDSCAPE)
    watermark_font_size = max(10, _safe_int_key("landscape_watermark_font_size", 27))
    bilingual_offset = _safe_int_key("landscape_bilingual_translation_offset", 0)
    cache_key = hashlib.sha1(
        (
            f"{SUBTITLE_STYLE_VERSION}|{src_srt}|{trans_srt}|{target_width}|{target_height}|"
            f"{watermark_offset}|{watermark_font_size}|{bilingual_offset}|"
            f"{os.path.getmtime(src_srt)}|{os.path.getmtime(trans_srt)}"
        ).encode("utf-8")
    ).hexdigest()[:16]
    ass_path = os.path.join(OUTPUT_DIR, "cache", f"landscape_watermark_{cache_key}.ass")
    subtitle_top_ys = _landscape_bilingual_entry_top_ys(
        src_srt, trans_srt, target_width, target_height
    )
    alpha = max(0, min(255, int(round((1.0 - WATERMARK_OPACITY) * 255))))
    primary_color = f"&H{alpha:02X}FFFFFF"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {target_width}
PlayResY: {target_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Watermark,{FONT_NAME},{watermark_font_size},{primary_color},{primary_color},&HFF000000,&HFF000000,0,0,0,0,100,100,0,0,1,0,0,2,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    center_x = int(target_width) // 2
    for index in range(count):
        start = min(src_entries[index]["start"], trans_entries[index]["start"])
        end = max(src_entries[index]["end"], trans_entries[index]["end"])
        watermark_bottom = _clamp(
            _landscape_watermark_bottom_y(subtitle_top_ys[index], watermark_offset),
            watermark_font_size,
            target_height,
        )
        lines.append(
            f"Dialogue: 0,{_ass_timestamp(start)},{_ass_timestamp(end)},Watermark,,0,0,0,,"
            f"{{\\an2\\pos({center_x},{watermark_bottom})}}{WATERMARK_TEXT}\n"
        )
    with open(ass_path, "w", encoding="utf-8") as file:
        file.writelines(lines)
    return ass_path

def _subtitle_filters_for_mode(
    src_srt=None,
    trans_srt=None,
    subtitle_mode="bilingual_src_top",
    target_width=None,
    target_height=None,
    layout=SUBTITLE_LAYOUT_LANDSCAPE,
    source_hardsub_box=None,
    portrait_layout=None,
):
    # ── Portrait path ──
    if layout == SUBTITLE_LAYOUT_PORTRAIT and target_width and target_height:
        if source_hardsub_box and subtitle_mode != "source_only":
            return [
                f"subtitles={_create_translation_avoiding_hardsub_ass(trans_srt, target_width, target_height, source_hardsub_box, portrait_layout)}"
            ]
        if _is_bilingual_mode(subtitle_mode):
            return [
                f"subtitles={_create_portrait_bilingual_ass(src_srt, trans_srt, subtitle_mode, target_width, target_height, portrait_layout)}"
            ]
        src_size, trans_size = _portrait_font_sizes(target_width)
        margin_v = _portrait_subtitle_margin_v(target_height)
        margin_h = _portrait_safe_side_margin(target_width)
        return _build_default_subtitle_filters(src_srt, trans_srt, subtitle_mode, src_size, trans_size, margin_v, margin_h)

    # ── Landscape path ──
    if target_width and target_height:
        if _is_bilingual_mode(subtitle_mode):
            return [
                f"subtitles={_create_landscape_bilingual_ass(src_srt, trans_srt, subtitle_mode, target_width, target_height)}"
            ]
        if subtitle_mode in ("source_only", "translation_only"):
            single_srt = src_srt if subtitle_mode == "source_only" else trans_srt
            return [
                f"subtitles={_create_landscape_single_ass(single_srt, subtitle_mode, target_width, target_height)}"
            ]
        src_size, trans_size, margin_v, margin_h = _landscape_subtitle_style(target_width, target_height)
        return _build_default_subtitle_filters(src_srt, trans_srt, subtitle_mode, src_size, trans_size, margin_v, margin_h)

    # ── Fallback (no dimensions available) ──
    src_size, trans_size = SRC_FONT_SIZE, TRANS_FONT_SIZE
    return _build_default_subtitle_filters(src_srt, trans_srt, subtitle_mode, src_size, trans_size, 20, None)

def _build_default_subtitle_filters(src_srt, trans_srt, subtitle_mode, src_size, trans_size, margin_v, margin_h):
    """Build non-bilingual ffmpeg subtitle filters from style parameters."""
    if subtitle_mode == "source_only":
        return [
            _subtitle_filter(src_srt, src_size, FONT_NAME, SRC_FONT_COLOR, SRC_OUTLINE_COLOR, SRC_OUTLINE_WIDTH, margin_v=margin_v, border_style=1, margin_l=margin_h, margin_r=margin_h)
        ]
    if subtitle_mode == "translation_only":
        return [
            _subtitle_filter(trans_srt, trans_size, TRANS_FONT_NAME, TRANS_FONT_COLOR, TRANS_OUTLINE_COLOR, TRANS_OUTLINE_WIDTH, margin_v=margin_v, back_color=TRANS_BACK_COLOR, margin_l=margin_h, margin_r=margin_h)
        ]
    if subtitle_mode in ("bilingual_trans_top", "single_bilingual_trans_top"):
        return [
            _subtitle_filter(trans_srt, trans_size, TRANS_FONT_NAME, TRANS_FONT_COLOR, TRANS_OUTLINE_COLOR, TRANS_OUTLINE_WIDTH, margin_v=margin_v, back_color=TRANS_BACK_COLOR, margin_l=margin_h, margin_r=margin_h),
            _subtitle_filter(src_srt, src_size, FONT_NAME, SRC_FONT_COLOR, SRC_OUTLINE_COLOR, SRC_OUTLINE_WIDTH, margin_v=margin_v, border_style=1, margin_l=margin_h, margin_r=margin_h),
        ]
    # bilingual_src_top (default)
    return [
        _subtitle_filter(src_srt, src_size, FONT_NAME, SRC_FONT_COLOR, SRC_OUTLINE_COLOR, SRC_OUTLINE_WIDTH, margin_v=margin_v, border_style=1, margin_l=margin_h, margin_r=margin_h),
        _subtitle_filter(trans_srt, trans_size, TRANS_FONT_NAME, TRANS_FONT_COLOR, TRANS_OUTLINE_COLOR, TRANS_OUTLINE_WIDTH, margin_v=margin_v, back_color=TRANS_BACK_COLOR, margin_l=margin_h, margin_r=margin_h),
    ]


def _watermark_drawtext_filter(
    target_height,
    layout=SUBTITLE_LAYOUT_LANDSCAPE,
    target_width=None,
    source_hardsub_box=None,
    portrait_layout=None,
    landscape_subtitle_top_y=None,
):
    """Build FFmpeg drawtext filter for watermark, positioned well above the subtitles."""
    wm_font_size = _watermark_font_size_for_video(target_width if layout == SUBTITLE_LAYOUT_PORTRAIT else None)
    watermark_y_expression = None
    if portrait_layout and layout == SUBTITLE_LAYOUT_PORTRAIT:
        base_y = int(portrait_layout.watermark.top)
    elif source_hardsub_box and layout == SUBTITLE_LAYOUT_PORTRAIT and target_width:
        base_y = int(_hardsub_translation_geometry(source_hardsub_box, target_width, target_height)["watermark_y"])
    elif layout == SUBTITLE_LAYOUT_PORTRAIT:
        base_y = int(round(target_height * 0.65)) - _effective_watermark_offset(layout=layout)
    else:
        wm_font_size = max(10, _safe_int_key("landscape_watermark_font_size", 27))
        if landscape_subtitle_top_y is not None:
            watermark_bottom_y = _clamp(
                int(landscape_subtitle_top_y)
                - LANDSCAPE_WATERMARK_SUBTITLE_GAP
                - _effective_watermark_offset(layout=layout),
                0,
                target_height,
            )
            watermark_y_expression = f"{watermark_bottom_y}-text_h"
            base_y = 0
        else:
            base_y = target_height - 246 - _effective_watermark_offset(layout=layout)
    watermark_y = _clamp(base_y, 0, max(0, target_height - wm_font_size))
    watermark_y_value = watermark_y_expression or str(watermark_y)
    font_color = f'white@{WATERMARK_OPACITY}'
    return (
        f"drawtext=text='{WATERMARK_TEXT}':"
        f"fontsize={wm_font_size}:"
        f"fontcolor={font_color}:"
        f"fontfile={WATERMARK_FONT_FILE}:"
        f"x=(w-text_w)/2:"
        f"y={watermark_y_value}"
    )

def _validate_subtitle_inputs(src_srt=None, trans_srt=None, subtitle_mode="bilingual_src_top"):
    missing = []
    if subtitle_mode == "source_only" and (not src_srt or not os.path.exists(src_srt)):
        missing.append(str(src_srt))
    if subtitle_mode == "translation_only" and (not trans_srt or not os.path.exists(trans_srt)):
        missing.append(str(trans_srt))
    if _is_bilingual_mode(subtitle_mode):
        for srt in (src_srt, trans_srt):
            if not srt or not os.path.exists(srt):
                missing.append(str(srt))
    if missing:
        raise FileNotFoundError(f"Subtitle file not found: {', '.join(missing)}")

def _video_filter_for_subtitles(target_width, target_height, src_srt=None, trans_srt=None, subtitle_mode="bilingual_src_top", watermark_enabled=False, video_file=None):
    layout = _subtitle_layout_for_video(target_width, target_height)
    source_hardsub_box = _source_hardsub_box_for_video(video_file, subtitle_mode, target_width, target_height, layout)
    portrait_layout = None
    if layout == SUBTITLE_LAYOUT_PORTRAIT and (
        source_hardsub_box or _is_bilingual_mode(subtitle_mode)
    ):
        portrait_layout = _portrait_layout_for_subtitles(
            src_srt,
            trans_srt,
            subtitle_mode,
            target_width,
            target_height,
            source_hardsub_box,
        )
    subtitle_filters = _subtitle_filters_for_mode(
        src_srt,
        trans_srt,
        subtitle_mode,
        target_width,
        target_height,
        layout,
        source_hardsub_box,
        portrait_layout,
    )
    filters = [
        f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease",
        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2",
    ]
    if watermark_enabled:
        if layout == SUBTITLE_LAYOUT_LANDSCAPE and _is_bilingual_mode(subtitle_mode):
            filters.append(
                f"subtitles={_create_landscape_watermark_ass(src_srt, trans_srt, target_width, target_height)}"
            )
        else:
            filters.append(
                _watermark_drawtext_filter(
                    target_height,
                    layout,
                    target_width,
                    source_hardsub_box,
                    portrait_layout,
                )
            )
    filters.extend(subtitle_filters)
    return ",".join(filters)

def render_subtitle_preview_frame(
    video_file,
    output_image,
    src_srt=None,
    trans_srt=None,
    subtitle_mode="bilingual_src_top",
    seek_time=1.0,
    watermark_enabled=False,
):
    _validate_subtitle_inputs(src_srt, trans_srt, subtitle_mode)
    os.makedirs(os.path.dirname(output_image), exist_ok=True)
    video = cv2.VideoCapture(video_file)
    target_width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    target_height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video.release()
    video_filter = _video_filter_for_subtitles(target_width, target_height, src_srt, trans_srt, subtitle_mode, watermark_enabled=watermark_enabled, video_file=video_file)
    command = [
        "ffmpeg", "-i", video_file,
        "-ss", str(max(0, float(seek_time))),
        "-vf", video_filter.encode("utf-8"),
        "-frames:v", "1",
        "-q:v", "2",
        "-y", output_image,
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            format_process_error(
                "FFmpeg preview generation",
                result.returncode,
                result.stderr,
            )
        )
    return output_image

def burn_subtitles_to_video(
    video_file,
    output_video=OUTPUT_VIDEO,
    src_srt=None,
    trans_srt=None,
    subtitle_mode="bilingual_src_top",
    watermark_enabled=None,
):
    if watermark_enabled is None:
        try:
            watermark_enabled = load_key("watermark_enabled")
        except Exception:
            watermark_enabled = False
    os.makedirs(os.path.dirname(output_video), exist_ok=True)

    # Check resolution
    if not load_key("burn_subtitles"):
        rprint("[bold yellow]Warning: A 0-second black video will be generated as a placeholder as subtitles are not burned in.[/bold yellow]")

        # Create a black frame
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_video, fourcc, 1, (1920, 1080))
        out.write(frame)
        out.release()

        rprint("[bold green]Placeholder video has been generated.[/bold green]")
        return output_video

    if not os.path.exists(video_file):
        raise FileNotFoundError(f"Video file not found: {video_file}")

    _validate_subtitle_inputs(src_srt, trans_srt, subtitle_mode)

    video = cv2.VideoCapture(video_file)
    TARGET_WIDTH = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    TARGET_HEIGHT = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video.release()
    video_filter = _video_filter_for_subtitles(TARGET_WIDTH, TARGET_HEIGHT, src_srt, trans_srt, subtitle_mode, watermark_enabled=watermark_enabled, video_file=video_file)
    rprint(f"[bold green]Video resolution: {TARGET_WIDTH}x{TARGET_HEIGHT}[/bold green]")
    ffmpeg_cmd = [
        'ffmpeg', '-i', video_file,
        '-vf', video_filter.encode('utf-8'),
    ]

    ffmpeg_gpu = load_key("ffmpeg_gpu")
    if ffmpeg_gpu:
        rprint("[bold green]will use GPU acceleration.[/bold green]")
        ffmpeg_cmd.extend(['-c:v', 'h264_nvenc'])
    ffmpeg_cmd.extend(['-y', output_video])

    rprint("🎬 Start merging subtitles to video...")
    start_time = time.time()
    process = subprocess.Popen(ffmpeg_cmd)

    try:
        process.wait()
        if process.returncode == 0:
            rprint(f"\n✅ Done! Time taken: {time.time() - start_time:.2f} seconds")
        else:
            raise RuntimeError(
                format_process_error(
                    "FFmpeg subtitle burn-in",
                    process.returncode,
                    "",
                )
            )
    except Exception as e:
        rprint(f"\n❌ Error occurred: {e}")
        if process.poll() is None:
            process.kill()
        raise
    return output_video

def merge_subtitles_to_video(
    video_file=None,
    output_video=None,
    src_srt=None,
    trans_srt=None,
    subtitle_mode="bilingual_trans_top",
    watermark_enabled=None,
):
    if watermark_enabled is None:
        try:
            watermark_enabled = load_key("watermark_enabled")
        except Exception:
            watermark_enabled = False
    if video_file is None:
        video_file = find_video_files()
    if output_video is None:
        output_video = get_default_output_video_path(
            video_file,
            subtitle_mode=subtitle_mode,
            avoid_overwrite=True,
        )
    subtitle_paths = get_default_subtitle_paths(video_file)
    src_srt = src_srt or subtitle_paths["src"]
    trans_srt = trans_srt or subtitle_paths["trans"]

    if subtitle_mode in ("source_only", "bilingual_src_top", "bilingual_trans_top", "single_bilingual_trans_top") and not os.path.exists(src_srt):
        rprint("Subtitle files not found in the 'output' directory.")
        exit(1)
    if subtitle_mode in ("translation_only", "bilingual_src_top", "bilingual_trans_top", "single_bilingual_trans_top") and not os.path.exists(trans_srt):
        rprint("Subtitle files not found in the 'output' directory.")
        exit(1)

    merged_video = burn_subtitles_to_video(
        video_file=video_file,
        output_video=output_video,
        src_srt=src_srt,
        trans_srt=trans_srt,
        subtitle_mode=subtitle_mode,
        watermark_enabled=watermark_enabled,
    )
    record_subtitle_merge(
        video_file=video_file,
        output_video=merged_video,
        src_srt=src_srt,
        trans_srt=trans_srt,
        subtitle_mode=subtitle_mode,
    )
    return merged_video

if __name__ == "__main__":
    merge_subtitles_to_video()
