# Remove FunASR From VideoLingo

## Goal

Remove the FunASR integration completely because its VAD and timestamp paths are not reliable enough for this VideoLingo workflow. Keep WhisperX and MLX Whisper as the supported local ASR runtimes.

## Scope

- Remove the FunASR backend module and its dedicated tests.
- Remove FunASR runtime and model controls from the Streamlit sidebar.
- Remove FunASR dispatching from the ASR pipeline.
- Remove FunASR-only configuration, translations, diagnostics, and requirements.
- Change an existing `whisper.runtime: funasr` setting to `mlx` so the application remains usable after removal.
- Uninstall the `funasr`, `qwen-asr`, and `modelscope` packages when they are not required by another retained package.
- Delete downloaded FunASR, Qwen3-ASR, SenseVoice, Paraformer, and FSMN VAD model caches.

## Exclusions

- Do not remove or alter WhisperX or MLX Whisper.
- Do not remove videos, subtitles, translation results, history, or other project output.
- Do not refactor unrelated subtitle, translation, rendering, or task-management code.

## Resulting ASR Flow

The GUI offers two runtimes:

1. WhisperX / faster-whisper for stricter word alignment.
2. MLX Whisper / Metal for Apple Silicon acceleration.

The selected runtime is saved through the existing `whisper.runtime` setting. Existing invalid or removed runtime values fall back to MLX Whisper.

## Error Handling

- Startup must not import FunASR packages or modules.
- A stale `funasr` runtime value must not crash the sidebar or transcription pipeline.
- No source file, translation entry, requirement, or test may retain a FunASR model/runtime reference.

## Verification

- Search the retained application source for FunASR, SenseVoice, Paraformer, Qwen3-ASR, and Fun-ASR model references.
- Validate `config.yaml` and translation JSON files.
- Compile the modified Python modules.
- Run WhisperX, MLX Whisper, translation, and timestamp regression tests.
- Import the Streamlit application modules without FunASR installed.
- Confirm the removed Python packages and model cache directories are absent.

