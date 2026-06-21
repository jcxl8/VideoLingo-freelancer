from core.utils import *
from core.utils.models import *

LOCAL_ASR_SEGMENT_SECONDS = 30
LOCAL_ASR_SEGMENT_SEARCH_WINDOW = 10
SUPPORTED_ASR_RUNTIMES = ("local", "mlx")


def resolve_asr_runtime(value):
    runtime = str(value or "").strip()
    return runtime if runtime in SUPPORTED_ASR_RUNTIMES else "mlx"

@check_file_exists(_2_CLEANED_CHUNKS)
def transcribe():
    from core._1_ytdlp import find_video_files
    from core.asr_backend.audio_preprocess import (
        convert_video_to_audio,
        normalize_audio_volume,
        process_transcription,
        save_results,
        split_audio,
    )
    from core.asr_backend.demucs_vl import demucs_audio

    # 1. video to audio
    video_file = find_video_files()
    if not video_file:
        raise RuntimeError("No source video found in output. Please download or upload a video before starting subtitle processing.")
    convert_video_to_audio(video_file)

    # 2. Demucs vocal separation:
    if load_key("demucs"):
        demucs_audio()
        vocal_audio = normalize_audio_volume(_VOCAL_AUDIO_FILE, _VOCAL_AUDIO_FILE, format="mp3")
    else:
        vocal_audio = _RAW_AUDIO_FILE

    # 4. Transcribe audio by clips.
    all_results = []
    runtime = resolve_asr_runtime(load_key("whisper.runtime"))
    if runtime == "mlx":
        from core.asr_backend.mlx_whisper_local import transcribe_audio_segments as ts_batch
        rprint("[cyan]🎤 Transcribing audio with MLX Whisper / Metal...[/cyan]")
    else:
        from core.asr_backend.whisperX_local import transcribe_audio_segments as ts_batch
        rprint("[cyan]🎤 Transcribing audio with local WhisperX model...[/cyan]")

    # Long single-pass transcription can miss speech islands on documentary
    # or news audio. Use shorter chunks while keeping the model loaded once
    # inside transcribe_audio_segments().
    segments = split_audio(
        _RAW_AUDIO_FILE,
        target_len=LOCAL_ASR_SEGMENT_SECONDS,
        win=LOCAL_ASR_SEGMENT_SEARCH_WINDOW,
    )
    all_results.append(ts_batch(_RAW_AUDIO_FILE, vocal_audio, segments))
    
    # 5. Combine results
    combined_result = {'segments': []}
    for result in all_results:
        combined_result['segments'].extend(result['segments'])
    
    # 6. Process df
    df = process_transcription(combined_result)
    save_results(df)
        
if __name__ == "__main__":
    transcribe()
