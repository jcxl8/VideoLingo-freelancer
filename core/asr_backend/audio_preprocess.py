import os, subprocess, json
import pandas as pd
from typing import Dict, List, Tuple
from pydub import AudioSegment
from core.utils import *
from core.utils.models import *
from pydub import AudioSegment
from pydub.silence import detect_silence
from pydub.utils import mediainfo
from rich import print as rprint

FILLER_WORDS = {
    "um", "uh", "umm", "uhh", "er", "erm", "hmm", "mm", "mhm",
    "eh",
}
REPEATABLE_FILLER_CONNECTORS = {"and", "but", "so", "like"}
NONREPEATABLE_DUPLICATE_WORDS = {
    "a", "an", "the",
    "of", "to", "in", "on", "at", "by", "for", "from", "with", "without",
}
REPEATABLE_EMPHASIS_WORDS = {
    "no", "yes", "yeah", "yep", "okay", "ok", "very", "really",
    "never", "more", "again",
}
NEAR_DUPLICATE_CONTENT_MAX_GAP_SECONDS = 0.5
NEAR_DUPLICATE_CONTENT_MAX_OVERLAP_SECONDS = 0.08
NEAR_DUPLICATE_CONTENT_MIN_TOKEN_LEN = 4
NEAR_DUPLICATE_SUBTOKEN_MAX_GAP_SECONDS = 0.5
NEAR_DUPLICATE_SUBTOKEN_MAX_OVERLAP_SECONDS = 0.8
NEAR_DUPLICATE_SUBTOKEN_MIN_TOKEN_LEN = 4

def _normalize_english_pronoun_i(text: str) -> str:
    raw = str(text)
    leading = raw[:len(raw) - len(raw.lstrip())]
    trailing = raw[len(raw.rstrip()):]
    core = raw.strip()
    prefix = core[:len(core) - len(core.lstrip(".,!?;:，。！？；：“”\"'()[]{}"))]
    suffix = core[len(core.rstrip(".,!?;:，。！？；：“”\"'()[]{}")):]
    token = core[len(prefix):len(core) - len(suffix) if suffix else len(core)]
    contractions = {
        "i": "I",
        "i'm": "I'm",
        "i’m": "I’m",
        "i've": "I've",
        "i’ve": "I’ve",
        "i'll": "I'll",
        "i’ll": "I’ll",
        "i'd": "I'd",
        "i’d": "I’d",
    }
    if token in contractions:
        return f"{leading}{prefix}{contractions[token]}{suffix}{trailing}"
    return raw

def _clean_word_token(text: str) -> str:
    return str(text).strip().strip(".,!?;:，。！？；：“”\"'()[]{}").lower()

def _is_filler_word(text: str) -> bool:
    return _clean_word_token(text) in FILLER_WORDS

def _contextual_word_artifact_mask(df: pd.DataFrame) -> pd.Series:
    if df.empty or "text" not in df.columns:
        return pd.Series(False, index=df.index, dtype=bool)

    tokens = [_clean_word_token(word) for word in df["text"]]
    duplicate_mask = []
    for index, token in enumerate(tokens):
        next_token = tokens[index + 1] if index + 1 < len(tokens) else ""
        duplicate_mask.append(token == "won" and next_token == "wanted")
    return pd.Series(duplicate_mask, index=df.index, dtype=bool)

def _apply_contextual_word_corrections(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    if df.empty or "text" not in df.columns:
        return df, 0

    df = df.copy()
    tokens = [_clean_word_token(word) for word in df["text"]]
    corrected_count = 0
    for index, token in enumerate(tokens):
        previous_token = tokens[index - 1] if index > 0 else ""
        if previous_token == "national" and token == "all":
            df.at[df.index[index], "text"] = "Mall"
            corrected_count += 1
        next_token = tokens[index + 1] if index + 1 < len(tokens) else ""
        if token == "africa" and next_token == "americans":
            df.at[df.index[index], "text"] = "African"
            corrected_count += 1
    return df, corrected_count

def _near_duplicate_content_mask(
    df: pd.DataFrame,
    max_gap: float = NEAR_DUPLICATE_CONTENT_MAX_GAP_SECONDS,
) -> pd.Series:
    if df.empty or not {"text", "start", "end"}.issubset(df.columns):
        return pd.Series(False, index=df.index, dtype=bool)

    duplicate_mask = []
    previous_token = ""
    previous_end = None
    for _, row in df.iterrows():
        current_token = _clean_word_token(row["text"])
        current_start = float(row["start"])
        current_end = float(row["end"])
        gap = None if previous_end is None else current_start - previous_end
        is_content_token = (
            len(current_token) >= NEAR_DUPLICATE_CONTENT_MIN_TOKEN_LEN
            and current_token not in REPEATABLE_FILLER_CONNECTORS
            and current_token not in REPEATABLE_EMPHASIS_WORDS
        )
        is_overlapping_repeat = (
            bool(current_token)
            and current_token == previous_token
            and gap is not None
            and -NEAR_DUPLICATE_CONTENT_MAX_OVERLAP_SECONDS <= gap < 0
        )
        duplicate_mask.append(
            bool(current_token)
            and current_token == previous_token
            and gap is not None
            and (
                (is_content_token and -NEAR_DUPLICATE_CONTENT_MAX_OVERLAP_SECONDS <= gap <= max_gap)
                or is_overlapping_repeat
            )
        )
        previous_token = current_token
        previous_end = current_end
    return pd.Series(duplicate_mask, index=df.index, dtype=bool)

def _near_duplicate_subtoken_mask(
    df: pd.DataFrame,
    max_gap: float = NEAR_DUPLICATE_SUBTOKEN_MAX_GAP_SECONDS,
) -> pd.Series:
    if df.empty or not {"text", "start", "end"}.issubset(df.columns):
        return pd.Series(False, index=df.index, dtype=bool)

    duplicate_mask = []
    previous_token = ""
    previous_start = None
    previous_end = None
    for _, row in df.iterrows():
        current_token = _clean_word_token(row["text"])
        current_start = float(row["start"])
        gap = None if previous_end is None else current_start - previous_end
        overlap = 0.0 if previous_end is None else previous_end - current_start
        is_suffix_fragment = (
            len(current_token) >= NEAR_DUPLICATE_SUBTOKEN_MIN_TOKEN_LEN
            and len(previous_token) >= len(current_token) + 3
            and previous_token.endswith(current_token)
        )
        duplicate_mask.append(
            bool(current_token)
            and bool(previous_token)
            and is_suffix_fragment
            and gap is not None
            and gap <= max_gap
            and overlap <= NEAR_DUPLICATE_SUBTOKEN_MAX_OVERLAP_SECONDS
            and (previous_start is None or current_start >= previous_start)
        )
        previous_token = current_token
        previous_start = current_start
        previous_end = float(row["end"])
    return pd.Series(duplicate_mask, index=df.index, dtype=bool)

def _format_srt_time(seconds: float) -> str:
    seconds = max(0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    whole_seconds = int(seconds % 60)
    milliseconds = int(round((seconds - int(seconds)) * 1000))
    if milliseconds >= 1000:
        whole_seconds += 1
        milliseconds -= 1000
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"

def _write_abnormal_word_report(df: pd.DataFrame, threshold: float):
    report_items = []
    if df.empty or not {"text", "start", "end"}.issubset(df.columns):
        return report_items

    work_df = df.reset_index(drop=True).copy()
    work_df["duration"] = work_df["end"].astype(float) - work_df["start"].astype(float)
    abnormal_rows = work_df[work_df["duration"] > threshold]

    for row_index, row in abnormal_rows.iterrows():
        previous_row = work_df.iloc[row_index - 1] if row_index > 0 else None
        next_row = work_df.iloc[row_index + 1] if row_index + 1 < len(work_df) else None
        start = float(row["start"])
        end = float(row["end"])
        item = {
            "word_index": int(row_index + 1),
            "word": str(row["text"]),
            "start": start,
            "end": end,
            "duration": round(end - start, 3),
            "timestamp": f"{_format_srt_time(start)} --> {_format_srt_time(end)}",
            "previous_word": "" if previous_row is None else str(previous_row["text"]),
            "next_word": "" if next_row is None else str(next_row["text"]),
            "reason": f"ASR word timestamp duration exceeds {threshold:.1f}s; this may indicate missed speech or bad alignment.",
        }
        report_items.append(item)

    for path in (_2_ABNORMAL_WORDS, _2_ABNORMAL_WORDS_MD):
        if not report_items and os.path.exists(path):
            os.remove(path)

    if not report_items:
        return report_items

    with open(_2_ABNORMAL_WORDS, "w", encoding="utf-8") as f:
        json.dump(report_items, f, ensure_ascii=False, indent=2)

    lines = [
        "# ASR Abnormal Word Timestamp Report",
        "",
        f"Detected words with duration longer than {threshold:.1f}s.",
        "",
    ]
    for item in report_items:
        lines.extend([
            f"## {item['word_index']}. {item['word']} · {item['timestamp']}",
            f"- Duration: {item['duration']}s",
            f"- Previous word: {item['previous_word']}",
            f"- Next word: {item['next_word']}",
            f"- Reason: {item['reason']}",
            "",
        ])
    with open(_2_ABNORMAL_WORDS_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

    rprint(
        f"[yellow]⚠️ Detected {len(report_items)} ASR word timestamp(s) longer than "
        f"{threshold:.1f}s. Report saved to {_2_ABNORMAL_WORDS_MD}[/yellow]"
    )
    return report_items

def _write_asr_quality_report(df: pd.DataFrame, abnormal_word_items=None):
    abnormal_word_items = abnormal_word_items or []
    timestamp_quality_counts = {}
    if not df.empty and "timestamp_quality" in df.columns:
        quality_series = df["timestamp_quality"].fillna("").astype(str)
        timestamp_quality_counts = {
            key: int(value)
            for key, value in quality_series[quality_series != ""].value_counts().to_dict().items()
        }
    report = {
        "summary": {
            "total_words": int(len(df)),
            "abnormal_word_count": int(len(abnormal_word_items)),
            "long_gap_count": 0,
            "repeated_word_count": 0,
            "bad_timestamp_count": 0,
        },
        "abnormal_words": abnormal_word_items,
        "long_gaps": [],
        "repeated_words": [],
        "bad_timestamps": [],
        "timestamp_quality_counts": timestamp_quality_counts,
    }
    if df.empty or not {"text", "start", "end"}.issubset(df.columns):
        return report

    work_df = df.reset_index(drop=True).copy()
    work_df["start"] = work_df["start"].astype(float)
    work_df["end"] = work_df["end"].astype(float)
    long_gap_threshold = 3.0

    for index, row in work_df.iterrows():
        duration = float(row["end"] - row["start"])
        if duration < 0:
            report["bad_timestamps"].append({
                "word_index": int(index + 1),
                "word": str(row["text"]),
                "start": float(row["start"]),
                "end": float(row["end"]),
                "reason": "Word end time is earlier than start time.",
            })
        if index == 0:
            continue
        prev = work_df.iloc[index - 1]
        gap = float(row["start"] - prev["end"])
        if gap > long_gap_threshold:
            report["long_gaps"].append({
                "after_word_index": int(index),
                "before_word": str(prev["text"]),
                "after_word": str(row["text"]),
                "gap": round(gap, 3),
                "timestamp": f"{_format_srt_time(float(prev['end']))} --> {_format_srt_time(float(row['start']))}",
                "reason": "Long gap between ASR words; check for missed speech or silence.",
            })
        prev_token = _clean_word_token(prev["text"])
        token = _clean_word_token(row["text"])
        if token and token == prev_token and token not in REPEATABLE_EMPHASIS_WORDS:
            report["repeated_words"].append({
                "word_index": int(index + 1),
                "word": str(row["text"]),
                "previous_word": str(prev["text"]),
                "timestamp": f"{_format_srt_time(float(prev['start']))} --> {_format_srt_time(float(row['end']))}",
                "reason": "Adjacent repeated word may be ASR duplication.",
            })

    report["summary"]["long_gap_count"] = len(report["long_gaps"])
    report["summary"]["repeated_word_count"] = len(report["repeated_words"])
    report["summary"]["bad_timestamp_count"] = len(report["bad_timestamps"])

    if not any(report["summary"][key] for key in ("abnormal_word_count", "long_gap_count", "repeated_word_count", "bad_timestamp_count")):
        for path in (_2_ASR_QUALITY_REPORT, _2_ASR_QUALITY_REPORT_MD):
            if os.path.exists(path):
                os.remove(path)
        return report

    with open(_2_ASR_QUALITY_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    lines = [
        "# ASR Quality Report",
        "",
        "This report highlights ASR timing and token risks before translation.",
        "",
        "## Summary",
        "",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- {key}: {value}")
    if timestamp_quality_counts:
        lines.extend(["", "## Timestamp Quality", ""])
        for key, value in timestamp_quality_counts.items():
            lines.append(f"- {key}: {value}")
    for section, title in [
        ("long_gaps", "Long Gaps"),
        ("repeated_words", "Repeated Words"),
        ("bad_timestamps", "Bad Timestamps"),
        ("abnormal_words", "Abnormal Word Durations"),
    ]:
        if report[section]:
            lines.extend(["", f"## {title}", ""])
            for item in report[section][:80]:
                lines.append("- " + "; ".join(f"{k}: {v}" for k, v in item.items()))
    with open(_2_ASR_QUALITY_REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    rprint(f"[yellow]⚠️ ASR quality report saved to {_2_ASR_QUALITY_REPORT_MD}[/yellow]")
    return report

def _ffmpeg_has_encoder(encoder_name: str) -> bool:
    """Check if the current ffmpeg installation supports a given audio encoder."""
    try:
        result = subprocess.run(
            ['ffmpeg', '-encoders'], capture_output=True, text=True, timeout=10
        )
        return encoder_name in result.stdout
    except Exception:
        return False

def _validate_ffmpeg_cmd(cmd: List[str]):
    bad_args = [
        (index, value)
        for index, value in enumerate(cmd)
        if value is None or not isinstance(value, (str, bytes, os.PathLike))
    ]
    if bad_args:
        details = ", ".join(f"#{index}={value!r}" for index, value in bad_args)
        raise RuntimeError(f"Invalid FFmpeg command argument(s): {details}")

def normalize_audio_volume(audio_path, output_path, target_db = -20.0, format = "wav"):
    audio = AudioSegment.from_file(audio_path)
    change_in_dBFS = target_db - audio.dBFS
    normalized_audio = audio.apply_gain(change_in_dBFS)
    normalized_audio.export(output_path, format=format)
    rprint(f"[green]✅ Audio normalized from {audio.dBFS:.1f}dB to {target_db:.1f}dB[/green]")
    return output_path

def convert_video_to_audio(video_file: str):
    if not video_file:
        raise RuntimeError("No source video found. Please download or upload a video before extracting audio.")
    if not _RAW_AUDIO_FILE:
        raise RuntimeError("Raw audio output path is not configured.")
    os.makedirs(_AUDIO_DIR, exist_ok=True)
    if not os.path.exists(_RAW_AUDIO_FILE):
        rprint(f"[blue]🎬➡️🎵 Converting to high quality audio with FFmpeg ......[/blue]")
        if _ffmpeg_has_encoder('libmp3lame'):
            cmd = [
                'ffmpeg', '-y', '-i', video_file, '-vn',
                '-c:a', 'libmp3lame', '-b:a', '32k',
                '-ar', '16000', '-ac', '1',
                '-metadata', 'encoding=UTF-8', _RAW_AUDIO_FILE
            ]
        else:
            # Fallback: conda-forge ffmpeg often lacks libmp3lame.
            # Output as WAV (PCM) which all ffmpeg builds support.
            # Downstream readers (pydub, librosa, whisperX) detect format by
            # file header, not extension, so .mp3 path with WAV content works.
            rprint("[yellow]⚠️ libmp3lame not found in ffmpeg, falling back to WAV (PCM) encoding[/yellow]")
            cmd = [
                'ffmpeg', '-y', '-i', video_file, '-vn',
                '-c:a', 'pcm_s16le', '-ar', '16000', '-ac', '1',
                '-f', 'wav', _RAW_AUDIO_FILE
            ]
        _validate_ffmpeg_cmd(cmd)
        subprocess.run(cmd, check=True, stderr=subprocess.PIPE)
        rprint(f"[green]🎬➡️🎵 Converted <{video_file}> to <{_RAW_AUDIO_FILE}> with FFmpeg\n[/green]")

def get_audio_duration(audio_file: str) -> float:
    """Get the duration of an audio file using ffmpeg."""
    cmd = ['ffmpeg', '-i', audio_file]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _, stderr = process.communicate()
    output = stderr.decode('utf-8', errors='ignore')
    
    try:
        duration_str = [line for line in output.split('\n') if 'Duration' in line][0]
        duration_parts = duration_str.split('Duration: ')[1].split(',')[0].split(':')
        duration = float(duration_parts[0])*3600 + float(duration_parts[1])*60 + float(duration_parts[2])
    except Exception as e:
        print(f"[red]❌ Error: Failed to get audio duration: {e}[/red]")
        duration = 0
    return duration


def _merge_short_final_segment(
    segments: List[Tuple[float, float]],
    min_duration: float = 3.0,
) -> List[Tuple[float, float]]:
    """Merge an undersized final remainder into its preceding ASR window."""
    merged = list(segments)
    if len(merged) < 2:
        return merged

    final_start, final_end = merged[-1]
    if final_end - final_start >= min_duration:
        return merged

    previous_start, _ = merged[-2]
    merged[-2:] = [(previous_start, final_end)]
    return merged


def split_audio(audio_file: str, target_len: float = 30*60, win: float = 60) -> List[Tuple[float, float]]:
    ## 在 [target_len-win, target_len+win] 区间内用 pydub 检测静默，切分音频
    rprint(f"[blue]🎙️ Starting audio segmentation {audio_file} {target_len} {win}[/blue]")
    audio = AudioSegment.from_file(audio_file)
    duration = float(mediainfo(audio_file)["duration"])
    if duration <= target_len + win:
        return [(0, duration)]
    segments, pos = [], 0.0
    safe_margin = 0.5  # 静默点前后安全边界，单位秒

    while pos < duration:
        if duration - pos <= target_len:
            segments.append((pos, duration)); break

        threshold = pos + target_len
        ws, we = int((threshold - win) * 1000), int((threshold + win) * 1000)
        
        # 获取完整的静默区域
        silence_regions = detect_silence(audio[ws:we], min_silence_len=int(safe_margin*1000), silence_thresh=-30)
        silence_regions = [(s/1000 + (threshold - win), e/1000 + (threshold - win)) for s, e in silence_regions]
        # 筛选长度足够（至少1秒）且位置适合的静默区域
        valid_regions = [
            (start, end) for start, end in silence_regions 
            if (end - start) >= (safe_margin * 2) and threshold <= start + safe_margin <= threshold + win
        ]
        
        if valid_regions:
            start, end = valid_regions[0]
            split_at = start + safe_margin  # 在静默区域起始点后0.5秒处切分
        else:
            rprint(f"[yellow]⚠️ No valid silence regions found for {audio_file} at {threshold}s, using threshold[/yellow]")
            split_at = threshold
            
        segments.append((pos, split_at)); pos = split_at

    original_count = len(segments)
    segments = _merge_short_final_segment(segments)
    if len(segments) < original_count:
        rprint("[blue]ℹ️ Merged a short final audio remainder into the previous ASR segment.[/blue]")
    rprint(f"[green]🎙️ Audio split completed {len(segments)} segments[/green]")
    return segments

def process_transcription(result: Dict) -> pd.DataFrame:
    all_words = []
    for segment in result['segments']:
        # Get speaker_id, if not exists, set to None
        speaker_id = segment.get('speaker_id', None)
        segment_asr_runtime = segment.get("asr_runtime")
        segment_timestamp_source = segment.get("timestamp_source")
        segment_timestamp_quality = segment.get("timestamp_quality")
        segment_timestamp_warning = segment.get("timestamp_warning")
        
        for word in segment['words']:
            # Check word length
            if len(word["word"]) > 30:
                rprint(f"[yellow]⚠️ Warning: Detected word longer than 30 characters, skipping: {word['word']}[/yellow]")
                continue
                
            # ! For French, we need to convert guillemets to empty strings
            word["word"] = word["word"].replace('»', '').replace('«', '')
            
            if 'start' not in word and 'end' not in word:
                if all_words:
                    # Assign the end time of the previous word as the start and end time of the current word
                    word_dict = {
                        'text': word["word"],
                        'start': all_words[-1]['end'],
                        'end': all_words[-1]['end'],
                        'speaker_id': speaker_id
                    }
                    _attach_asr_metadata(
                        word_dict, word, segment_asr_runtime,
                        segment_timestamp_source, segment_timestamp_quality,
                        segment_timestamp_warning,
                    )
                    all_words.append(word_dict)
                else:
                    # If it's the first word, look next for a timestamp then assign it to the current word
                    next_word = next((w for w in segment['words'] if 'start' in w and 'end' in w), None)
                    if next_word:
                        word_dict = {
                            'text': word["word"],
                            'start': next_word["start"],
                            'end': next_word["end"],
                            'speaker_id': speaker_id
                        }
                        _attach_asr_metadata(
                            word_dict, word, segment_asr_runtime,
                            segment_timestamp_source, segment_timestamp_quality,
                            segment_timestamp_warning,
                        )
                        all_words.append(word_dict)
                    else:
                        raise Exception(f"No next word with timestamp found for the current word : {word}")
            else:
                # Normal case, with start and end times
                word_dict = {
                    'text': f'{word["word"]}',
                    'start': word.get('start', all_words[-1]['end'] if all_words else 0),
                    'end': word['end'],
                    'speaker_id': speaker_id
                }
                _attach_asr_metadata(
                    word_dict, word, segment_asr_runtime,
                    segment_timestamp_source, segment_timestamp_quality,
                    segment_timestamp_warning,
                )
                
                all_words.append(word_dict)
    
    df = pd.DataFrame(all_words)
    if not df.empty and {"start", "end"}.issubset(df.columns):
        df = df.sort_values(["start", "end"], kind="stable").reset_index(drop=True)
    return df


def _attach_asr_metadata(word_dict, word, segment_asr_runtime=None, segment_timestamp_source=None, segment_timestamp_quality=None, segment_timestamp_warning=None):
    for key, segment_value in (
        ("asr_runtime", segment_asr_runtime),
        ("timestamp_source", segment_timestamp_source),
        ("timestamp_quality", segment_timestamp_quality),
        ("timestamp_warning", segment_timestamp_warning),
    ):
        value = word.get(key, segment_value)
        if value:
            word_dict[key] = value

def save_results(df: pd.DataFrame):
    if df.empty or 'text' not in df.columns:
        rprint('[yellow]⚠️ No transcription results to save — DataFrame is empty or missing text column.[/yellow]')
        return
    os.makedirs('output/log', exist_ok=True)
    df = df.copy()
    df['text'] = df['text'].apply(_normalize_english_pronoun_i)

    # Remove rows where 'text' is empty
    initial_rows = len(df)
    df = df[df['text'].str.len() > 0]
    removed_rows = initial_rows - len(df)
    if removed_rows > 0:
        rprint(f"[blue]ℹ️ Removed {removed_rows} row(s) with empty text.[/blue]")
    
    # Check for and remove words longer than 20 characters
    long_words = df[df['text'].str.len() > 30]
    if not long_words.empty:
        rprint(f"[yellow]⚠️ Warning: Detected {len(long_words)} word(s) longer than 30 characters. These will be removed.[/yellow]")
        df = df[df['text'].str.len() <= 30]

    # Remove ASR filler words that harm sentence splitting and subtitle alignment.
    initial_rows = len(df)
    df = df[~df['text'].apply(_is_filler_word)].copy()
    removed_fillers = initial_rows - len(df)
    if removed_fillers > 0:
        rprint(f"[blue]ℹ️ Removed {removed_fillers} filler word(s) such as um/uh before subtitle splitting.[/blue]")

    df, corrected_contextual_words = _apply_contextual_word_corrections(df)
    if corrected_contextual_words > 0:
        rprint(f"[blue]ℹ️ Corrected {corrected_contextual_words} contextual ASR word(s) before subtitle splitting.[/blue]")

    duplicate_mask = []
    previous_word = ""
    for word in df['text']:
        current_word = _clean_word_token(word)
        duplicate_mask.append(
            bool(current_word)
            and current_word == previous_word
            and current_word in (REPEATABLE_FILLER_CONNECTORS | NONREPEATABLE_DUPLICATE_WORDS)
        )
        previous_word = current_word
    duplicate_mask = pd.Series(duplicate_mask, index=df.index, dtype=bool)
    duplicate_count = int(duplicate_mask.sum())
    if duplicate_count:
        df = df[~duplicate_mask].copy()
        rprint(f"[blue]ℹ️ Removed {duplicate_count} repeated filler connector(s) after ASR cleanup.[/blue]")

    contextual_artifact_mask = _contextual_word_artifact_mask(df)
    contextual_artifact_count = int(contextual_artifact_mask.sum())
    if contextual_artifact_count:
        removed_words = ", ".join(
            str(word) for word in df.loc[contextual_artifact_mask, "text"].head(5).tolist()
        )
        df = df[~contextual_artifact_mask].copy()
        rprint(
            f"[blue]ℹ️ Removed {contextual_artifact_count} contextual ASR artifact word(s): "
            f"{removed_words}[/blue]"
        )

    near_duplicate_mask = _near_duplicate_content_mask(df)
    near_duplicate_count = int(near_duplicate_mask.sum())
    if near_duplicate_count:
        removed_words = ", ".join(
            str(word) for word in df.loc[near_duplicate_mask, "text"].head(5).tolist()
        )
        df = df[~near_duplicate_mask].copy()
        rprint(
            f"[blue]ℹ️ Removed {near_duplicate_count} near-duplicate ASR content word(s) "
            f"within {NEAR_DUPLICATE_CONTENT_MAX_GAP_SECONDS:.1f}s: {removed_words}[/blue]"
        )

    subtoken_duplicate_mask = _near_duplicate_subtoken_mask(df)
    subtoken_duplicate_count = int(subtoken_duplicate_mask.sum())
    if subtoken_duplicate_count:
        removed_words = ", ".join(
            str(word) for word in df.loc[subtoken_duplicate_mask, "text"].head(5).tolist()
        )
        df = df[~subtoken_duplicate_mask].copy()
        rprint(
            f"[blue]ℹ️ Removed {subtoken_duplicate_count} near-duplicate ASR suffix fragment(s): "
            f"{removed_words}[/blue]"
        )

    subtitle_config = load_key("subtitle") or {}
    abnormal_word_threshold = float(subtitle_config.get("abnormal_word_duration", 3.0))
    abnormal_word_items = _write_abnormal_word_report(df, abnormal_word_threshold)
    _write_asr_quality_report(df, abnormal_word_items)
    
    df['text'] = df['text'].apply(lambda x: f'"{x}"')
    df.to_excel(_2_CLEANED_CHUNKS, index=False)
    rprint(f"[green]📊 Excel file saved to {_2_CLEANED_CHUNKS}[/green]")

def save_language(language: str):
    update_key("whisper.detected_language", language)
