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

- Python 3.12
- FFmpeg
- macOS, Windows, or Linux
- Apple Silicon or an NVIDIA GPU is recommended for longer videos, but is not required for every workflow

### Install and start

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python install.py
```

To start it again later:

```bash
streamlit run st.py
```

### Apple Silicon and MLX Whisper

```bash
pip install mlx-whisper
```

Select `MLX Whisper / Metal` in the ASR Runtime control. On non-macOS systems, select `WhisperX / faster-whisper` and use the `large-v3` model.

## ⚙️ Configuration

The default `config.yaml` contains public placeholders only. Real credentials should be placed in environment variables or `.streamlit/secrets.toml`, which is excluded from Git:

```toml
VIDEOLINGO_API_KEY = "your-workflow-model-key"
VIDEOLINGO_TRANSLATOR_API_KEY = "your-translation-model-key"
VIDEOLINGO_YOUTUBE_COOKIES_PATH = "/absolute/path/to/cookies.txt"
VIDEOLINGO_AZURE_TTS_API_KEY = "your-tts-key"
```

See [`core/utils/secret_store.py`](core/utils/secret_store.py) for every supported secret name. Model weights and runtime data under `output/`, `history/`, and `_model_cache/` are also excluded from Git.

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
