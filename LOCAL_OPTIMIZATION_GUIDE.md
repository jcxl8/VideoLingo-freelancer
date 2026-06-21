# VideoLingo Freelancer — Local Optimization Guide

This guide describes how to install, migrate, validate, and maintain the customized **VideoLingo Freelancer** workflow on another computer. It was audited against the active customized checkout and the public release on **2026-06-21**.

> Public source: <https://github.com/jcxl8/VideoLingo-freelancer.git>
>
> Upstream project: <https://github.com/Huanshere/VideoLingo>

The public repository is the portable baseline. A developer's working directory may also contain API keys, cookies, generated videos, model caches, logs, and unfinished experiments. Do not copy an entire local working directory to publish or migrate it.

## 1. What this edition adds

The customized workflow keeps VideoLingo's main pipeline while adding production-oriented local operation:

- separate translation and semantic-analysis model routes;
- platform-aware ASR: MLX Whisper on Apple Silicon macOS, and the regular Whisper/WhisperX path on other systems;
- independent portrait and landscape subtitle layouts with shared timing and segmentation logic;
- configurable watermark rendering;
- automatic ambiguity checks, translation refinement, and subtitle proofreading;
- retranslating and manually re-merging intermediate results without restarting the whole job;
- copy-first upload handling so source files are not moved or damaged;
- atomic task state, resumable steps, structured error reporting, and per-job manifests;
- preview caches and history-video helpers;
- secret migration, tracked-secret scanning, regression tests, and CI dependency checks.

The Streamlit interface remains available for interactive use. Automation tools such as Codex, Claude Code, and OpenClaw can operate the same checkout through its scripts and task modules without depending on browser clicks.

## 2. Supported environments

Recommended baseline:

- Python 3.12;
- FFmpeg and FFprobe available on `PATH`;
- Git;
- macOS, Windows, or Linux;
- enough disk space for ASR models and rendered video.

ASR defaults:

| Platform | Preferred backend | Default model |
| --- | --- | --- |
| Apple Silicon macOS | MLX Whisper | `large-v3` |
| Windows or Linux | Whisper/WhisperX-compatible backend | `large-v3` |
| Intel macOS | Regular Whisper-compatible backend | `large-v3` |

MLX is an Apple Silicon optimization and must not be made a mandatory dependency on Windows or Linux. The implementation lives in `core/asr_backend/mlx_whisper_local.py`; platform detection must retain a non-MLX fallback.

## 3. Recommended installation

Clone the curated public release instead of copying selected Python files from a private working tree:

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer

python3.12 -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python install.py
```

If `install.py` is unsuitable for the target machine, install from the repository's requirement files and keep the same Python interpreter for installation and execution:

```bash
python -m pip install -r requirements.txt
```

For development and CI checks:

```bash
python -m pip install -r requirements-ci.txt
```

Start the interface only after validation succeeds:

```bash
streamlit run st.py
```

## 4. Updating an existing installation

Back up only intentional local configuration, then update through Git:

```bash
git status --short
git fetch origin
git pull --ff-only
```

Do not overwrite a customized checkout blindly. If the installation contains private modifications, compare them explicitly and port only intentional changes:

```bash
git diff --stat
git diff -- config.yaml core st.py
```

The following are code and should normally come from the repository:

- `core/`
- `scripts/`
- `tests/`
- `st.py`
- `install.py`
- requirement and constraint files
- public example configuration

Machine-specific values belong in environment variables or untracked secret files, not in committed Python or YAML.

## 5. Secrets and private data

Never publish or casually migrate real credentials. In particular, do not commit:

- `.streamlit/secrets.toml`;
- real API keys in `config.yaml`;
- browser cookies or cookie files;
- service-account files;
- private proxy URLs;
- personal absolute paths.

Supported secret sources include environment variables and Streamlit secrets. Common variables include:

```bash
export VIDEOLINGO_API_KEY="replace-me"
export VIDEOLINGO_TRANSLATOR_API_KEY="replace-me"
export VIDEOLINGO_COOKIE_PATH="/absolute/path/to/private/cookies.txt"
```

Relevant security modules and tools:

- `core/utils/secret_store.py` — reads secrets without writing them into public config;
- `scripts/migrate_config_secrets.py` — migrates legacy inline secrets;
- `scripts/check_tracked_secrets.py` — fails when tracked files appear to contain secrets.

Run migration in preview mode before applying it:

```bash
python scripts/migrate_config_secrets.py --help
```

Review the command's options and generated changes before deleting any legacy values.

## 6. Data that should stay local

These directories and files are runtime data, not source-code migration material:

- `output/`
- `history/`
- `_model_cache/`
- downloaded models and media;
- log files and crash dumps;
- cookies and `.streamlit/secrets.toml`;
- temporary spreadsheets and subtitle intermediates;
- `.DS_Store`, virtual environments, and Python caches.

Copy generated media separately only when it is intentionally required. Do not add it to the Git repository.

## 7. Current architecture map

### 7.1 ASR and platform selection

- `core/asr_backend/mlx_whisper_local.py` implements local MLX Whisper support.
- The normal Whisper/WhisperX route remains the cross-platform fallback.
- Platform selection should happen at runtime; importing MLX must not break a non-Mac installation.
- ASR model caches stay outside source control.

When changing ASR behavior, verify actual returned text and timestamp fields. Different model families may return `timestamp` or `timestamps`, and word-level data may be dictionaries or lists.

### 7.2 Translation and semantic routing

- `core/utils/model_router.py` separates translator and semantic-analysis requests.
- Translation concurrency is controlled independently from semantic-analysis calls.
- Configuration must use placeholders; real provider credentials come from the secret store.

This separation prevents expensive translation calls from being accidentally reused for segmentation, checking, or analysis tasks.

### 7.3 Subtitle segmentation and layouts

- `core/subtitle_layout.py` resolves portrait and landscape layout settings.
- Shared code owns timestamps, semantic splitting, and bilingual alignment.
- Rendering code owns layout-specific line width, font size, margins, and watermark offset.
- Portrait and landscape values must not silently overwrite one another.

The pipeline should preserve existing bilingual structure when bilingual output is selected. If an intermediate spreadsheet changes, remove stale split intermediates before rerunning semantic alignment.

### 7.4 Proofreading and controlled rework

- `core/subtitle_proofread.py` performs subtitle-level checks and corrections.
- `core/st_utils/retranslation.py` reruns translation without repeating unrelated earlier steps.
- `core/st_utils/manual_merge_files.py` supports controlled manual re-merge workflows.
- Ambiguity checks, workflow refinement, and automatic proofread are separate switches and should be tested independently.

Proofreading must preserve timing order and subtitle count unless a documented repair explicitly changes segmentation.

### 7.5 Tasks, recovery, and atomic writes

- `core/st_utils/task_runner.py` coordinates long-running operations.
- `core/st_utils/task_state.py` records resumable task state.
- `core/utils/atomic_files.py` prevents partially written state and configuration files.
- `core/utils/process_errors.py` normalizes subprocess failures for the interface and CLI callers.
- `core/job_manifest.py` records reproducible per-job metadata.

Task state is operational metadata. It should describe a job without embedding raw credentials.

### 7.6 Uploads, history, and previews

- `core/st_utils/upload_copy.py` copies uploaded input into the workspace instead of moving the original.
- `core/st_utils/history_video.py` manages safe history-video access.
- `core/st_utils/subtitle_preview_cache.py` caches preview work without treating cache files as source.

File names from uploads must be sanitized, and resolved paths must remain inside their intended runtime directories.

### 7.7 Structured data and normalization

- `core/utils/structured_cells.py` reads structured spreadsheet cells safely.
- `core/utils/text_normalize.py` centralizes text normalization.

Do not replace structured parsing with unrestricted `eval`. Spreadsheet-derived content is untrusted input.

## 8. Configuration checklist

Use the checked-in example as a schema and keep actual credentials elsewhere. Confirm these functional areas after installation:

```yaml
whisper:
  model: large-v3
  runtime: mlx        # Apple Silicon macOS; select the regular backend elsewhere

subtitle_layout: portrait_9_16

watermark_enabled: true
watermark_text: "Your Name"

translator_refine_with_workflow: true
enable_ambiguity_check: true
enable_subtitle_proofread: true
```

Exact keys can evolve. Treat the repository's current `config.yaml` and configuration loader as authoritative, and never replace a newer config wholesale with an older private copy.

Check both layout profiles:

- portrait: line length, font size, vertical position, bilingual spacing, watermark offset;
- landscape: its own line length, font size, vertical position, bilingual spacing, watermark offset.

## 9. Validation and regression gates

Run all commands from the repository root with the target virtual environment active.

### 9.1 Security and repository checks

```bash
python scripts/check_tracked_secrets.py
git status --short
git diff --check
```

### 9.2 Local structural validation

```bash
python scripts/validate_local.py
python scripts/run_regression_checks.py
```

### 9.3 Syntax and unit tests

```bash
PYTHONPYCACHEPREFIX=/tmp/videolingo-pycache \
  python -m compileall -q core scripts st.py

python -m unittest discover -v tests
```

The public CI dependency set is declared in `requirements-ci.txt`. Keep it synchronized with modules imported by the test suite. Runtime dependency pins or generated constraints should be refreshed with the repository tools rather than edited casually.

### 9.4 Smoke test

```bash
streamlit run st.py
```

Then verify:

1. the app starts without importing MLX on an unsupported platform;
2. a short file can be copied into a job safely;
3. ASR selects the expected backend;
4. translation and semantic models can be configured separately;
5. portrait and landscape previews use independent settings;
6. proofreading and retranslating do not restart unrelated completed stages;
7. task state can resume after an intentional interruption;
8. final subtitles and rendered video are written to runtime output, not the repository.

## 10. CI and release hygiene

Before publishing:

```bash
python scripts/check_tracked_secrets.py
python scripts/validate_local.py
python scripts/run_regression_checks.py
python -m unittest discover -v tests
git diff --check
```

Also inspect tracked paths for private data:

```bash
git ls-files | grep -E '(^|/)(output|history|_model_cache|logs?)/' || true
git grep -nE '/Users/|[A-Za-z]:\\Users\\' -- ':!*.md' || true
```

A clean release must contain no real secrets, no personal absolute paths in executable configuration, and no generated media.

## 11. Troubleshooting

### MLX fails to import

- Confirm the machine is Apple Silicon macOS.
- Confirm the active Python interpreter is the one where MLX dependencies were installed.
- On Windows, Linux, or Intel macOS, select the regular Whisper-compatible backend.

### FFmpeg is missing

Confirm both executables resolve from the same terminal that starts VideoLingo:

```bash
ffmpeg -version
ffprobe -version
```

### Translation or semantic analysis uses the wrong model

Check the separate translator and semantic-analysis configuration, then confirm the active secret provider. Do not solve routing problems by duplicating API keys into tracked YAML.

### Subtitle alignment fails after editing an intermediate spreadsheet

The split cache may belong to an older spreadsheet. Back up the job, remove stale semantic/NLP split intermediates, and regenerate them from the current cleaned chunks.

### A task cannot resume

Inspect the job manifest and task-state file for the first failed stage. Atomic files should either contain a complete previous state or a complete new state; a manually edited partial JSON file should be discarded only after backing it up.

### Tests pass locally but CI fails

Use Python 3.12, install `requirements-ci.txt`, and compare the CI workflow interpreter and dependency set. Run the same discovery command used by CI rather than a subset.

## 12. Acceptance checklist

The migration or update is complete only when all of the following are true:

- the repository was cloned or updated from the public source;
- no real secrets or personal runtime data are tracked;
- the target platform selects a supported ASR backend;
- dual-model routing works with placeholder-free secrets supplied externally;
- portrait and landscape layouts remain independent;
- proofreading, retranslation, task recovery, and history helpers are available;
- security, validation, regression, syntax, and unit-test gates pass;
- one short end-to-end job produces the expected subtitles and video.

When upstream VideoLingo changes, rebase or merge deliberately, rerun the full gates, and update this guide whenever the module map or configuration contract changes.
