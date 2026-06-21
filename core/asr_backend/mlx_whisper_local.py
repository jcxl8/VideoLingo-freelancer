import os

from huggingface_hub import snapshot_download
from huggingface_hub.utils import disable_progress_bars
from rich import print as rprint

from core.utils import load_key, update_key


MLX_WHISPER_MODEL_REPOS = {
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
}

HIGH_NO_SPEECH_PROBABILITY = 0.8
LOW_WORD_PROBABILITY = 0.2
MIN_CREDIBLE_SEGMENT_SECONDS = 0.2


def resolve_mlx_whisper_model(model_name):
    model_repo = MLX_WHISPER_MODEL_REPOS.get(model_name, model_name)
    if os.path.exists(str(model_repo)):
        return model_repo
    if "/" not in str(model_repo):
        return model_repo

    disable_progress_bars()
    rprint(f"[green]📥 Preparing MLX Whisper model cache:[/green] {model_repo}")
    return snapshot_download(
        repo_id=model_repo,
        max_workers=1,
        tqdm_class=None,
        resume_download=True,
    )


def _word_has_timestamps(word):
    return "start" in word and "end" in word


def _is_suspicious_silent_segment(segment, words):
    no_speech_probability = segment.get("no_speech_prob")
    if no_speech_probability is None or float(no_speech_probability) < HIGH_NO_SPEECH_PROBABILITY:
        return False

    segment_start = float(segment.get("start", words[0]["start"]))
    segment_end = float(segment.get("end", words[-1]["end"]))
    has_zero_duration_word = any(
        float(word["end"]) <= float(word["start"])
        for word in words
    )
    has_low_confidence_word = any(
        "probability" in word and float(word["probability"]) < LOW_WORD_PROBABILITY
        for word in words
    )
    has_implausibly_short_duration = segment_end - segment_start < MIN_CREDIBLE_SEGMENT_SECONDS
    defect_count = sum((
        has_zero_duration_word,
        has_low_confidence_word,
        has_implausibly_short_duration,
    ))
    return defect_count >= 2


def _normalise_mlx_result(result):
    segments = []
    for segment in result.get("segments", []):
        words = []
        for word in segment.get("words", []):
            if not _word_has_timestamps(word):
                continue
            text = str(word.get("word", "")).strip()
            if not text:
                continue
            normalised_word = {
                "word": text,
                "start": float(word["start"]),
                "end": float(word["end"]),
            }
            if word.get("probability") is not None:
                normalised_word["probability"] = float(word["probability"])
            words.append(normalised_word)

        text = str(segment.get("text", "")).strip()
        if not words:
            continue

        if _is_suspicious_silent_segment(segment, words):
            rprint(
                "[yellow]⚠️ Rejected a likely silent ASR hallucination "
                f"at {float(segment.get('start', words[0]['start'])):.2f}s "
                f"(no_speech_prob={float(segment['no_speech_prob']):.3f}).[/yellow]"
            )
            continue

        normalised_segment = {
            "text": text or " ".join(word["word"] for word in words),
            "start": float(segment.get("start", words[0]["start"])),
            "end": float(segment.get("end", words[-1]["end"])),
            "words": words,
        }
        for key in ("avg_logprob", "no_speech_prob", "compression_ratio"):
            if segment.get(key) is not None:
                normalised_segment[key] = float(segment[key])
        segments.append(normalised_segment)
    return {"segments": segments, "language": result.get("language")}


def transcribe_audio_segments(raw_audio_file, vocal_audio_file, segments):
    try:
        import mlx_whisper
    except ImportError as exc:
        raise RuntimeError(
            "MLX Whisper is not installed. Install it with: pip install mlx-whisper"
        ) from exc

    whisper_language = load_key("whisper.language")
    model_name = load_key("whisper.model")
    model_repo = resolve_mlx_whisper_model(model_name)
    language = None if "auto" in str(whisper_language) else whisper_language

    rprint(f"[green]▶️ Starting MLX Whisper with Metal for {len(segments)} audio segment(s)...[/green]")
    rprint(f"[green]📥 MLX Whisper model:[/green] {model_repo}")

    # Pad audio with 1.5s silence to help Whisper detect the first speech segment.
    # Without padding, Whisper can miss the first 2-5s of speech, especially after
    # an abrupt start or loud intro audio.
    AUDIO_PAD_SECONDS = 1.5
    import tempfile, subprocess
    padded_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_audio_file,
         "-af", f"adelay={int(AUDIO_PAD_SECONDS * 1000)}|{int(AUDIO_PAD_SECONDS * 1000)}",
         "-ar", "16000", "-ac", "1", padded_file],
        capture_output=True, check=True,
    )
    rprint(f"[blue]🔇 Padded audio with {AUDIO_PAD_SECONDS}s silence to improve first-segment detection.[/blue]")

    combined_result = {"segments": []}
    for start, end in segments:
        rprint(f"[green]▶️ Starting MLX Whisper for segment {start:.2f}s to {end:.2f}s...[/green]")
        # Shift clip timestamps by the padding amount
        padded_start = float(start) + AUDIO_PAD_SECONDS
        padded_end = float(end) + AUDIO_PAD_SECONDS
        result = mlx_whisper.transcribe(
            padded_file,
            path_or_hf_repo=model_repo,
            word_timestamps=True,
            language=language,
            clip_timestamps=[padded_start, padded_end],
            condition_on_previous_text=False,
            temperature=0.0,
            hallucination_silence_threshold=1.0,
            verbose=False,
        )
        if result.get("language"):
            update_key("whisper.detected_language", result["language"])
            if str(whisper_language) != "auto":
                update_key("whisper.language", whisper_language)

        normalised = _normalise_mlx_result(result)
        # Subtract padding from all timestamps to restore original timing
        for seg in normalised["segments"]:
            seg["start"] = max(0.0, seg["start"] - AUDIO_PAD_SECONDS)
            seg["end"] = max(0.0, seg["end"] - AUDIO_PAD_SECONDS)
            for word in seg.get("words", []):
                word["start"] = max(0.0, word["start"] - AUDIO_PAD_SECONDS)
                word["end"] = max(0.0, word["end"] - AUDIO_PAD_SECONDS)
        combined_result["segments"].extend(normalised["segments"])

    # Clean up padded file
    import os as _os
    _os.unlink(padded_file)
    return combined_result


def transcribe_audio(raw_audio_file, vocal_audio_file, start, end):
    return transcribe_audio_segments(raw_audio_file, vocal_audio_file, [(start, end)])
