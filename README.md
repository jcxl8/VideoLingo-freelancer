<div align="center">

<img src="docs/logo.png" alt="VideoLingo-Freelancer Logo" height="140">

# VideoLingo-Freelancer

### Local video translation, subtitle production, and dubbing — built for independent creators

[![Quality](https://github.com/jcxl8/VideoLingo-freelancer/actions/workflows/quality.yml/badge.svg)](https://github.com/jcxl8/VideoLingo-freelancer/actions/workflows/quality.yml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

[**English**](README.md)｜[**简体中文**](translations/README.zh.md)｜[**Español**](translations/README.es.md)｜[**Русский**](translations/README.ru.md)｜[**Français**](translations/README.fr.md)｜[**Deutsch**](translations/README.de.md)｜[**Italiano**](translations/README.it.md)｜[**日本語**](translations/README.ja.md)

</div>

## 🌟 Overview

VideoLingo-Freelancer is a customized distribution of [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) for local, creator-oriented video localization. It brings transcription, translation, subtitle review, layout, burn-in, project recovery, and dubbing into one Streamlit workspace.

The project preserves the upstream Git history and Apache 2.0 license while adding a workflow tuned for both landscape videos and 9:16 vertical content. It is an independent derivative distribution, not an official VideoLingo release.

## 🤖 Agent Skill

Automate an installed VideoLingo-Freelancer workflow from **Codex, Claude Code, or OpenClaw** with the [VideoLingo-Freelancer Skill](https://github.com/jcxl8/videolingo-freelancer-skill). Its AgentSkills-compatible CLI orchestrator can prepare input, transcribe, translate, proofread, render, dub, and archive jobs from natural-language requests.

The Skill does not include this application’s source code, models, or credentials. Install and configure VideoLingo-Freelancer first, then connect the Skill to that existing checkout.

## ✨ Key Features

| Area | Capabilities |
| --- | --- |
| 🎙️ Local transcription | MLX Whisper on Apple Silicon or WhisperX / faster-whisper on other supported systems; Whisper large-v3 model |
| 🌍 Multilingual UI | Eight selectable interface languages with safe English fallback |
| 🧠 Dual-model translation | Separate workflow and translation models, including local OpenAI-compatible endpoints |
| 📝 Subtitle quality | Semantic splitting, bilingual output, ambiguity review, proofreading, and selective retranslation |
| 📱 Layout control | Independent landscape and 9:16 portrait sizes, offsets, hard-subtitle handling, and previews |
| 🏷️ Custom watermark | Configurable text, visibility, size, and vertical placement |
| ⏯️ Resumable tasks | Pause, resume, stop, and continue from a failed step after a Streamlit rerun |
| 🗂️ Project history | Archive source videos and subtitles, reopen a project, and re-merge previous results |
| 🔐 Local secrets | API credentials can stay in environment variables or an ignored Streamlit secrets file |

## 🧠 Local Translation Model

VideoLingo-Freelancer can send subtitle translation to a local **OpenAI-compatible** model endpoint while keeping workflow tasks—such as terminology, reflection, and quality review—on a separate model.

**Maintainer's tested recommendation:** on my **Mac mini M4 with 32 GB of unified memory**, I use and recommend Tencent's [Hy-MT2-7B](https://huggingface.co/tencent/Hy-MT2-7B). Its official model card describes it as a 7B multilingual translation model supporting translation among **33 languages**.

Connect an already running local model server through the translator profile:

```yaml
translator_api:
  key: sk-local
  base_url: http://127.0.0.1:8765/v1
  model: hy-mt2-7b
  llm_support_json: false
```

This is a personal, tested recommendation rather than a universal hardware minimum. Memory use and translation speed depend on the inference backend, model format, context length, and quantization. Follow the model card for supported deployment methods and inference parameters.

## 🔄 Workflow

```text
Download / Upload
        ↓
Local ASR transcription
        ↓
Semantic segmentation and terminology
        ↓
Translation, review, and proofreading
        ↓
Landscape / portrait subtitle rendering
        ↓
Video burn-in, archive, or dubbing
```

## 🌐 Language Support

### Interface Languages

| English | 简体中文 | Español | Русский |
| --- | --- | --- | --- |
| Français | Deutsch | Italiano | 日本語 |

Spanish, Russian, French, and Japanese reuse the upstream interface catalogs. German and Italian currently cover the core workflow. Any missing customized label falls back to English instead of breaking the interface.

### ASR Input Languages

Automatic detection is available together with:

🇺🇸 English · 🇨🇳 Chinese · 🇪🇸 Spanish · 🇷🇺 Russian · 🇫🇷 French · 🇩🇪 German · 🇮🇹 Italian · 🇯🇵 Japanese

Translation output can be configured independently. Available dubbing languages depend on the selected TTS backend.

## 🚀 Installation

### Requirements

- Git
- FFmpeg and FFprobe on `PATH`
- macOS, Windows, or Linux
- a small system Python only to run the bootstrap script; uv downloads the maintained Python 3.12 runtime
- Apple Silicon or an NVIDIA GPU is recommended for longer videos, but is not required for every workflow

Install FFmpeg before VideoLingo-Freelancer:

```bash
brew install ffmpeg                 # macOS with Homebrew
choco install ffmpeg                # Windows with Chocolatey
sudo apt update && sudo apt install ffmpeg  # Ubuntu / Debian
```

### Recommended: uv + Python 3.12

The bootstrapper follows the current upstream installation direction while retaining the Python 3.12 runtime tested by VideoLingo-Freelancer. It installs uv when necessary, creates `.venv`, installs all dependencies, and starts the app:

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer
python setup_env.py              # use python3 on macOS/Linux if needed
```

Install without launching the interface:

```bash
python setup_env.py --no-launch
```

Start it later with the environment-bound interpreter:

```bash
.venv/bin/python -m streamlit run st.py            # macOS / Linux
.venv\Scripts\python.exe -m streamlit run st.py    # Windows
```

Windows users can also double-click `OneKeyStart_uv.bat` after setup.

### Manual Python 3.12 fallback

If uv cannot be used, create a Python 3.12 virtual environment yourself and run the same installer:

```bash
python3.12 -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python install.py
```

Use `python install.py --no-launch` for unattended installation. The installer must run under Python 3.12 and always launches Streamlit through that same interpreter.

### Platform-specific speech dependencies

- **Apple Silicon macOS:** the conditional dependency installs `mlx-whisper==0.4.3`; select `MLX Whisper / Metal` with `large-v3`.
- **Windows or Linux with NVIDIA:** the installer detects the driver through `nvidia-smi` and selects a compatible PyTorch wheel before installing WhisperX.
- **CPU or Intel macOS:** the standard PyTorch build and WhisperX path remain available, but transcription is slower.

PyTorch and Demucs are intentionally installed by `install.py` rather than locked as universal wheels because CUDA indexes and torchaudio compatibility vary by platform. See [`docs/dependency-management.md`](docs/dependency-management.md).

## ⚙️ Configuration

The default `config.yaml` contains public placeholders only. Real credentials should be placed in environment variables or `.streamlit/secrets.toml`, which is excluded from Git:

```toml
VIDEOLINGO_API_KEY = "your-workflow-model-key"
VIDEOLINGO_TRANSLATOR_API_KEY = "your-translation-model-key"
VIDEOLINGO_YOUTUBE_COOKIES_PATH = "/absolute/path/to/cookies.txt"
VIDEOLINGO_AZURE_TTS_API_KEY = "your-tts-key"
```

See [`core/utils/secret_store.py`](core/utils/secret_store.py) for every supported secret name. Model weights and runtime data under `output/`, `history/`, and `_model_cache/` are also excluded from Git.

## 🗂️ Project Structure

```text
VideoLingo-freelancer/
├── st.py                       # Streamlit application entrypoint
├── setup_env.py                # uv + Python 3.12 environment bootstrap
├── install.py                  # Platform-aware dependency installer
├── setup.py                    # Python package metadata
├── config.yaml                 # Public configuration schema and defaults
├── core/
│   ├── _1_ytdlp.py ...         # Download, ASR, translation, subtitle, and dubbing stages
│   ├── asr_backend/             # MLX Whisper and WhisperX implementations
│   ├── tts_backend/             # Text-to-speech providers
│   ├── spacy_utils/             # NLP segmentation and source-quality helpers
│   ├── st_utils/                # UI tasks, history, previews, and recovery
│   ├── utils/                   # Config, secrets, model routing, and atomic files
│   ├── subtitle_formats.py      # Subtitle parsing and formatting
│   ├── subtitle_layout.py       # Portrait and landscape layout resolution
│   └── subtitle_proofread.py    # Subtitle quality gate
├── scripts/                     # Validation, migration, and maintenance tools
├── tests/                       # Unit and regression tests
├── translations/                # UI catalogs and localized README pages
├── docs/                        # Logos, dependency policy, and maintenance notes
├── batch/                       # Batch-processing helpers
├── requirements.txt             # Cross-platform runtime dependencies
├── requirements-ci.txt          # Deterministic CI dependencies
└── constraints-py312.txt        # Python 3.12 dependency snapshot
```

Runtime directories such as `output/`, `history/`, and `_model_cache/` are created locally as needed. They can contain generated media, project archives, and model weights, so they are excluded from Git.

## ✅ Validation

```bash
python scripts/check_tracked_secrets.py
python scripts/validate_local.py
python scripts/run_regression_checks.py
python -m compileall -q core scripts st.py
python -m unittest discover -v tests
```

The same core checks run automatically in GitHub Actions.

## ⚠️ Current Limitations

1. German and Italian currently translate core workflow controls; less common customized labels may appear in English.
2. Local ASR models and model weights are downloaded separately and can require substantial disk space.
3. Whisper word alignment can be less reliable with heavy background music, mixed languages, numbers, or unusual names. Voice separation may help noisy material.
4. Translation quality depends on the configured models and API compatibility. Weak models may produce malformed structured responses.
5. Dubbing quality varies with the TTS backend, speaking rate, voice, and source-audio quality.

## 📚 Maintenance Notes

- [`LOCAL_OPTIMIZATION_GUIDE.md`](LOCAL_OPTIMIZATION_GUIDE.md) — customized local workflow
- [`docs/dependency-management.md`](docs/dependency-management.md) — dependency and CI policy
- [`docs/maintenance/`](docs/maintenance/) — source boundaries and maintenance notes

## 📄 License and Upstream

VideoLingo-Freelancer is licensed under the [Apache License 2.0](LICENSE).

This distribution is based on [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo). Thanks to its authors, contributors, and the open-source projects used throughout the original VideoLingo pipeline.

Please keep the license and upstream attribution when redistributing modified versions.

---

<p align="center">Built for practical, local-first video localization.</p>
