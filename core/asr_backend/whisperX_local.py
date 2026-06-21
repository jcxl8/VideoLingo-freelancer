import os
import json
import warnings
import time
import torch
import functools

warnings.filterwarnings("ignore")

# =============================================================================
# Compatibility shim — applied BEFORE importing whisperx
# =============================================================================

# torch.load: default weights_only=False for pyannote checkpoints
# PyTorch >=2.6 changed torch.load default to weights_only=True.
# pyannote checkpoints contain omegaconf objects that fail the safety check.
# Monkey-patch torch.load to default to weights_only=False (matching <2.6
# behavior).  This is safe here because all model files come from trusted
# sources (HuggingFace / pyannote).
_original_torch_load = torch.load
@functools.wraps(_original_torch_load)
def _patched_torch_load(*args, **kwargs):
    if kwargs.get("weights_only") is None:
        kwargs["weights_only"] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

# =============================================================================
# Now safe to import whisperx and the rest of the application
# =============================================================================
import whisperx
from whisperx.audio import load_audio as _whisperx_load_audio, SAMPLE_RATE as _WHISPERX_SR
from faster_whisper import WhisperModel
from rich import print as rprint
from core.utils import *
MODEL_DIR = load_key("model_dir")

WHISPER_MODEL_REPOS = {
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}
ASR_GAP_REPAIR_THRESHOLD = 3.5
ASR_GAP_REPAIR_MARGIN = 0.6
ASR_GAP_REPAIR_MAX_SECONDS = 60.0
ASR_GAP_REPAIR_CONTEXT_WORDS = 12
ASR_GAP_REPAIR_REPORT = "output/log/asr_gap_repair.json"

@except_handler("failed to check hf mirror", default_return=None)
def check_hf_mirror():
    endpoint = os.environ.get("VIDEOLINGO_HF_ENDPOINT", "https://huggingface.co").rstrip("/")
    rprint(f"[cyan]🚀 HuggingFace endpoint:[/cyan] {endpoint}")
    return endpoint

def _repo_cache_dir(repo_id):
    return os.path.join(MODEL_DIR, f"models--{repo_id.replace('/', '--')}")

def _read_ref(cache_dir, ref_name="main"):
    ref_path = os.path.join(cache_dir, "refs", ref_name)
    if not os.path.exists(ref_path):
        return None
    with open(ref_path, "r", encoding="utf-8") as file:
        return file.read().strip()

def _required_model_files_exist(model_dir):
    required_files = ["config.json", "model.bin", "tokenizer.json", "vocabulary.json"]
    return all(os.path.exists(os.path.join(model_dir, name)) for name in required_files)

def resolve_local_whisper_model(model_name):
    repo_id = WHISPER_MODEL_REPOS.get(model_name)
    if not repo_id:
        return model_name

    cache_dir = _repo_cache_dir(repo_id)
    commit_hash = _read_ref(cache_dir)
    if not commit_hash:
        return model_name

    snapshot_dir = os.path.join(cache_dir, "snapshots", commit_hash)
    if os.path.isdir(snapshot_dir) and _required_model_files_exist(snapshot_dir):
        rprint(f"[green]📥 Loading cached WHISPER model:[/green] {snapshot_dir} ...")
        return snapshot_dir

    rprint(
        f"[yellow]⚠️ Cached WHISPER model is incomplete, will download/repair from HuggingFace:[/yellow] "
        f"{repo_id}"
    )
    return model_name

def _iter_timed_words(result):
    for segment in result.get("segments", []):
        for word in segment.get("words", []):
            if "start" in word and "end" in word:
                yield word

def _asr_word_text(word):
    return str(word.get("word", "")).strip()

def _normalize_asr_token(text):
    return (
        str(text)
        .strip()
        .strip(".,!?;:，。！？；：“”\"'()[]{}")
        .lower()
    )

def _normalized_asr_tokens(words):
    return [
        _normalize_asr_token(_asr_word_text(word))
        for word in words
        if _normalize_asr_token(_asr_word_text(word))
    ]

def _trim_context_overlap(gap_words, left_context_words, right_context_words):
    candidate_words = list(gap_words)
    candidate_tokens = _normalized_asr_tokens(candidate_words)
    if not candidate_tokens:
        return []

    left_tokens = _normalized_asr_tokens(left_context_words)
    right_tokens = _normalized_asr_tokens(right_context_words)

    max_prefix = min(len(candidate_tokens), len(left_tokens), ASR_GAP_REPAIR_CONTEXT_WORDS)
    for overlap_len in range(max_prefix, 0, -1):
        if candidate_tokens[:overlap_len] == left_tokens[-overlap_len:]:
            candidate_words = candidate_words[overlap_len:]
            candidate_tokens = candidate_tokens[overlap_len:]
            break

    if not candidate_tokens:
        return []

    max_suffix = min(len(candidate_tokens), len(right_tokens), ASR_GAP_REPAIR_CONTEXT_WORDS)
    for overlap_len in range(max_suffix, 0, -1):
        if candidate_tokens[-overlap_len:] == right_tokens[:overlap_len]:
            candidate_words = candidate_words[:-overlap_len]
            candidate_tokens = candidate_tokens[:-overlap_len]
            break

    return candidate_words

def _format_repair_words(words):
    return " ".join(_asr_word_text(word) for word in words).strip()

def _write_asr_gap_repair_report(report_items):
    os.makedirs(os.path.dirname(ASR_GAP_REPAIR_REPORT), exist_ok=True)
    if not report_items:
        if os.path.exists(ASR_GAP_REPAIR_REPORT):
            os.remove(ASR_GAP_REPAIR_REPORT)
        return
    with open(ASR_GAP_REPAIR_REPORT, "w", encoding="utf-8") as file:
        json.dump(report_items, file, ensure_ascii=False, indent=2)

def _transcribe_plain_segments(model, audio_segment, whisper_language):
    transcribed_segments, info = model.transcribe(
        audio_segment,
        language=whisper_language,
        beam_size=5,
        best_of=5,
        temperature=0,
        vad_filter=False,
        condition_on_previous_text=False,
    )
    segments = [
        {
            "text": segment.text.strip(),
            "start": float(segment.start),
            "end": float(segment.end),
        }
        for segment in transcribed_segments
        if segment.text and segment.text.strip()
    ]
    return {"segments": segments, "language": info.language}

def _align_segments(model_a, metadata, vocal_audio_segment, device, result):
    if not result.get("segments"):
        return {"segments": [], "language": result.get("language")}
    aligned = whisperx.align(
        result["segments"],
        model_a,
        metadata,
        vocal_audio_segment,
        device,
        return_char_alignments=False,
    )
    aligned["language"] = result.get("language", aligned.get("language"))
    return aligned

def _shift_result_timestamps(result, offset):
    for segment in result.get("segments", []):
        segment["start"] += offset
        segment["end"] += offset
        for word in segment.get("words", []):
            if "start" in word:
                word["start"] += offset
            if "end" in word:
                word["end"] += offset
    return result

def _repair_transcription_gaps(
    combined_result,
    model,
    model_a,
    metadata,
    raw_audio,
    vocal_audio,
    device,
    whisper_language,
    detected_language,
):
    timed_words = sorted(
        list(_iter_timed_words(combined_result)),
        key=lambda word: (float(word["start"]), float(word["end"])),
    )
    if len(timed_words) < 2:
        return combined_result

    duration = len(raw_audio) / _WHISPERX_SR
    repaired_segments = []
    repair_report = []
    for word_index, (left, right) in enumerate(zip(timed_words, timed_words[1:])):
        gap_start = float(left["end"])
        gap_end = float(right["start"])
        gap = gap_end - gap_start
        if gap < ASR_GAP_REPAIR_THRESHOLD:
            continue
        if gap > ASR_GAP_REPAIR_MAX_SECONDS:
            repair_report.append({
                "status": "skipped_too_long",
                "gap_start": round(gap_start, 3),
                "gap_end": round(gap_end, 3),
                "gap_seconds": round(gap, 3),
                "previous_word": _asr_word_text(left),
                "next_word": _asr_word_text(right),
                "reason": (
                    f"Gap exceeds ASR gap repair limit "
                    f"{ASR_GAP_REPAIR_MAX_SECONDS:.1f}s."
                ),
            })
            continue

        clip_start = max(0.0, gap_start - ASR_GAP_REPAIR_MARGIN)
        clip_end = min(duration, gap_end + ASR_GAP_REPAIR_MARGIN)
        raw_clip = raw_audio[int(clip_start * _WHISPERX_SR):int(clip_end * _WHISPERX_SR)]
        vocal_clip = vocal_audio[int(clip_start * _WHISPERX_SR):int(clip_end * _WHISPERX_SR)]
        if len(raw_clip) <= 0:
            continue

        rprint(
            f"[yellow]🔎 Rechecking ASR gap {gap:.2f}s: "
            f"{gap_start:.2f}s -> {gap_end:.2f}s[/yellow]"
        )
        retry_result = _transcribe_plain_segments(model, raw_clip, whisper_language or detected_language)
        retry_result = _align_segments(model_a, metadata, vocal_clip, device, retry_result)
        retry_result = _shift_result_timestamps(retry_result, clip_start)

        gap_words = []
        for word in _iter_timed_words(retry_result):
            word_start = float(word["start"])
            word_end = float(word["end"])
            midpoint = (word_start + word_end) / 2
            if gap_start + 0.05 <= midpoint <= gap_end - 0.05:
                gap_words.append(dict(word))

        if not gap_words:
            repair_report.append({
                "status": "no_words",
                "gap_start": round(gap_start, 3),
                "gap_end": round(gap_end, 3),
                "gap_seconds": round(gap, 3),
                "previous_word": _asr_word_text(left),
                "next_word": _asr_word_text(right),
            })
            continue

        left_context_words = timed_words[
            max(0, word_index + 1 - ASR_GAP_REPAIR_CONTEXT_WORDS):word_index + 1
        ]
        right_context_words = timed_words[
            word_index + 1:word_index + 1 + ASR_GAP_REPAIR_CONTEXT_WORDS
        ]
        candidate_text = _format_repair_words(gap_words)
        gap_words = _trim_context_overlap(gap_words, left_context_words, right_context_words)
        repaired_text = _format_repair_words(gap_words)
        if not repaired_text:
            repair_report.append({
                "status": "skipped_duplicate_boundary",
                "gap_start": round(gap_start, 3),
                "gap_end": round(gap_end, 3),
                "gap_seconds": round(gap, 3),
                "previous_word": _asr_word_text(left),
                "next_word": _asr_word_text(right),
                "candidate_text": candidate_text,
            })
            continue

        repaired_segments.append({
            "text": repaired_text,
            "start": float(gap_words[0]["start"]),
            "end": float(gap_words[-1]["end"]),
            "words": gap_words,
        })
        repair_report.append({
            "status": "inserted",
            "gap_start": round(gap_start, 3),
            "gap_end": round(gap_end, 3),
            "gap_seconds": round(gap, 3),
            "previous_word": _asr_word_text(left),
            "next_word": _asr_word_text(right),
            "candidate_text": candidate_text,
            "inserted_text": repaired_text,
        })
        rprint(f"[green]✅ Repaired ASR gap with:[/green] {repaired_text}")

    _write_asr_gap_repair_report(repair_report)
    if repaired_segments:
        combined_result["segments"].extend(repaired_segments)
        rprint(f"[green]✅ ASR gap repair inserted {len(repaired_segments)} segment(s).[/green]")
    return combined_result

@except_handler("WhisperX processing error:")
def transcribe_audio(raw_audio_file, vocal_audio_file, start, end):
    return transcribe_audio_segments(raw_audio_file, vocal_audio_file, [(start, end)])

@except_handler("WhisperX processing error:")
def transcribe_audio_segments(raw_audio_file, vocal_audio_file, segments):
    os.environ['HF_ENDPOINT'] = check_hf_mirror()
    WHISPER_LANGUAGE = load_key("whisper.language")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    rprint(f"🚀 Starting WhisperX using device: {device} ...")
    
    if device == "cuda":
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        batch_size = 16 if gpu_mem > 8 else 2
        compute_type = "float16" if torch.cuda.is_bf16_supported() else "int8"
        rprint(f"[cyan]🎮 GPU memory:[/cyan] {gpu_mem:.2f} GB, [cyan]📦 Batch size:[/cyan] {batch_size}, [cyan]⚙️ Compute type:[/cyan] {compute_type}")
    else:
        batch_size = 1
        compute_type = "int8"
        rprint(f"[cyan]📦 Batch size:[/cyan] {batch_size}, [cyan]⚙️ Compute type:[/cyan] {compute_type}")
    rprint(f"[green]▶️ Starting WhisperX for {len(segments)} audio segment(s)...[/green]")
    
    if WHISPER_LANGUAGE == 'zh':
        model_name = "Huan69/Belle-whisper-large-v3-zh-punct-fasterwhisper"
        local_model = os.path.join(MODEL_DIR, "Belle-whisper-large-v3-zh-punct-fasterwhisper")
    else:
        model_name = load_key("whisper.model")
        local_model = os.path.join(MODEL_DIR, model_name)
        
    if os.path.exists(local_model):
        rprint(f"[green]📥 Loading local WHISPER model:[/green] {local_model} ...")
        model_name = local_model
    else:
        model_name = resolve_local_whisper_model(model_name)
        if not os.path.exists(model_name):
            rprint(f"[green]📥 Using WHISPER model from HuggingFace:[/green] {model_name} ...")

    whisper_language = None if 'auto' in WHISPER_LANGUAGE else WHISPER_LANGUAGE
    model = WhisperModel(
        model_name,
        device=device,
        compute_type=compute_type,
        download_root=MODEL_DIR,
        cpu_threads=4,
    )

    def slice_audio_segment(full_audio, start, end):
        # Use whisperx's ffmpeg-based loader instead of librosa.load() which
        # deadlocks inside Streamlit's ScriptRunner thread.
        start_sample = int(start * _WHISPERX_SR)
        end_sample = int(end * _WHISPERX_SR)
        return full_audio[start_sample:end_sample]

    raw_audio = _whisperx_load_audio(raw_audio_file, sr=_WHISPERX_SR)
    vocal_audio = _whisperx_load_audio(vocal_audio_file, sr=_WHISPERX_SR)
    combined_result = {"segments": []}
    model_a = None
    metadata = None

    try:
        for start, end in segments:
            rprint(f"[green]▶️ Starting WhisperX for segment {start:.2f}s to {end:.2f}s...[/green]")
            raw_audio_segment = slice_audio_segment(raw_audio, start, end)
            vocal_audio_segment = slice_audio_segment(vocal_audio, start, end)

            # -------------------------
            # 1. transcribe raw audio
            # -------------------------
            transcribe_start_time = time.time()
            rprint("[bold green]Note: You will see Progress if working correctly ↓[/bold green]")
            result = _transcribe_plain_segments(model, raw_audio_segment, whisper_language)
            transcribe_time = time.time() - transcribe_start_time
            rprint(f"[cyan]⏱️ time transcribe:[/cyan] {transcribe_time:.2f}s")

            # Save language
            detected_language = result.get('language') or WHISPER_LANGUAGE
            update_key("whisper.detected_language", detected_language)
            if WHISPER_LANGUAGE != "auto":
                update_key("whisper.language", WHISPER_LANGUAGE)
            if detected_language == 'zh' and WHISPER_LANGUAGE not in ('zh', 'auto'):
                raise ValueError("Please specify the transcription language as zh and try again!")
            if not result.get("segments"):
                continue

            # -------------------------
            # 2. align by vocal audio
            # -------------------------
            align_start_time = time.time()
            # Align timestamps using vocal audio
            if model_a is None:
                model_a, metadata = whisperx.load_align_model(language_code=detected_language, device=device)
            result = _align_segments(model_a, metadata, vocal_audio_segment, device, result)
            align_time = time.time() - align_start_time
            rprint(f"[cyan]⏱️ time align:[/cyan] {align_time:.2f}s")

            # Adjust timestamps
            result = _shift_result_timestamps(result, start)
            combined_result["segments"].extend(result["segments"])

        if model_a is not None:
            detected_language = load_key("whisper.detected_language")
            combined_result = _repair_transcription_gaps(
                combined_result,
                model,
                model_a,
                metadata,
                raw_audio,
                vocal_audio,
                device,
                whisper_language,
                detected_language,
            )
    finally:
        # Free resources
        del model
        if model_a is not None:
            del model_a
        torch.cuda.empty_cache()

    return combined_result
