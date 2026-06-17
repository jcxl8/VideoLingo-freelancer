# Remove FunASR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove FunASR from VideoLingo while keeping WhisperX and MLX Whisper operational.

**Architecture:** Collapse ASR runtime selection to `local` and `mlx`, normalize stale runtime values to `mlx`, and delete the isolated FunASR adapter. Remove FunASR-specific metadata, configuration, translations, packages, and model caches without touching project output.

**Tech Stack:** Python 3.12, Streamlit, YAML, JSON, unittest, pip.

---

### Task 1: Runtime migration and dispatch

**Files:**
- Create: `tests/test_asr_runtime.py`
- Modify: `core/_2_asr.py`
- Modify: `config.yaml`

- [ ] **Step 1: Write the failing runtime test**

```python
import unittest
from core import _2_asr

class ASRRuntimeTests(unittest.TestCase):
    def test_removed_runtime_falls_back_to_mlx(self):
        self.assertEqual(_2_asr.resolve_asr_runtime("funasr"), "mlx")
```

- [ ] **Step 2: Run the test and confirm it fails because the resolver is absent**

Run: `python -m unittest tests.test_asr_runtime -v`

- [ ] **Step 3: Add `SUPPORTED_ASR_RUNTIMES` and `resolve_asr_runtime`, remove FunASR dispatch, and set `whisper.runtime: mlx`**

```python
SUPPORTED_ASR_RUNTIMES = ("local", "mlx")

def resolve_asr_runtime(value):
    runtime = str(value or "").strip()
    return runtime if runtime in SUPPORTED_ASR_RUNTIMES else "mlx"
```

- [ ] **Step 4: Run `tests.test_asr_runtime` and confirm it passes**

### Task 2: Remove GUI and configuration surface

**Files:**
- Modify: `core/st_utils/sidebar_setting.py`
- Modify: `translations/en.json`
- Modify: `translations/zh-CN.json`

- [ ] **Step 1: Restrict sidebar runtime options to `local` and `mlx`, default stale values to `mlx`, and remove FunASR model controls/history keys**
- [ ] **Step 2: Replace the three-runtime help text with the existing WhisperX/MLX help text and remove FunASR translation keys**
- [ ] **Step 3: Validate both translation JSON files with `python -m json.tool`**

### Task 3: Remove backend, diagnostics, tests, and requirements

**Files:**
- Delete: `core/asr_backend/funasr_local.py`
- Delete: `tests/test_funasr_backend.py`
- Modify: `core/asr_backend/audio_preprocess.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Delete the isolated FunASR adapter and its dedicated test module**
- [ ] **Step 2: Remove `funasr_fallback_word_count` while retaining generic timestamp-quality reporting**
- [ ] **Step 3: Remove `funasr` and `qwen-asr` requirement entries**
- [ ] **Step 4: Search retained source and configuration for FunASR model/runtime references; expected result is empty**

### Task 4: Remove installed packages and model data

**Files:**
- Remove Python packages from the active environment: `funasr`, `qwen-asr`, `modelscope`
- Remove dedicated caches under Hugging Face and VideoLingo `_model_cache`

- [ ] **Step 1: Confirm none of the three packages is required by a retained package**
- [ ] **Step 2: Run `python -m pip uninstall -y funasr qwen-asr modelscope`**
- [ ] **Step 3: Delete only FunASR/Qwen-ASR/SenseVoice/Paraformer/FSMN-VAD cache directories**
- [ ] **Step 4: Verify package imports fail and cache directories are absent**

### Task 5: Full verification

**Files:**
- Test: `tests/test_asr_runtime.py`
- Test: `tests/test_mlx_whisper_backend.py`
- Test: `tests/test_whisperx_translations.py`
- Test: `tests/test_sentence_timestamp_fuzzy_alignment.py`

- [ ] **Step 1: Compile modified Python modules**
- [ ] **Step 2: Validate YAML and translation JSON**
- [ ] **Step 3: Run retained ASR and timestamp regression tests**
- [ ] **Step 4: Import `core._2_asr` and `core.st_utils.sidebar_setting` without FunASR installed**
- [ ] **Step 5: Confirm current videos, subtitles, output, and history remain untouched**

