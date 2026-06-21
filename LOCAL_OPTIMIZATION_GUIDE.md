# VideoLingo Local Dual-Model Optimization and Migration Guide

This guide explains how to reproduce the customized local VideoLingo workflow on another computer. The goal is to turn VideoLingo into a video-localization workstation that combines a local translation model with a workflow-oriented large language model.

## Goals

- Use a local translation-model endpoint for subtitle translation, such as Hy-MT, TranslateGemma, a llama.cpp server, LM Studio, or an Ollama-compatible endpoint.
- Use a workflow LLM for summaries, terminology extraction, translation reflection and refinement, ambiguity checks, subtitle quality review, and upload title and description generation.
- Preserve a human-review loop: show the ambiguity report after subtitle generation and merge the video only after confirmation.
- Support manual subtitle and video merging, subtitle-style previews, merged-video previews, and project-history archiving.
- Improve maintainability by separating the GUI, task state, model routing, and upload-copy modules.

## Supported Environments

- macOS or Linux.
- A Python environment capable of running VideoLingo.
- A local or remote OpenAI-compatible API:
  - Workflow model: JSON output support is preferred.
  - Translation model: this may be a local endpoint such as `http://127.0.0.1:xxxx/v1`.
- FFmpeg installed.
- When using local WhisperX, confirm that the required model and dependencies are available.

## Content That Must Not Be Migrated

Do not directly copy the following sensitive or machine-specific content:

- Real API keys stored in `config.yaml`.
- YouTube cookie file paths.
- `config_history.json`.
- `output/`, `history/`, or `_model_cache/`.
- `streamlit.log` or `streamlit.pid`.

After migration, enter the API keys, `BASE_URL`, model names, and cookie settings again through the GUI.

## Recommended Migration Methods

### Method A: Copy the Optimized Files

Copy the following files from the optimized computer to the same locations on the new computer:

```text
st.py
.gitignore
config.yaml
core/st_utils/upload_copy.py
core/st_utils/task_state.py
core/utils/model_router.py
core/utils/ask_gpt.py
core/utils/config_utils.py
core/utils/onekeycleanup.py
core/translate_lines.py
core/st_utils/sidebar_setting.py
translations/en.json
translations/zh-CN.json
scripts/validate_local.py
scripts/run_regression_checks.py
```

If the new computer contains a clean upstream VideoLingo checkout, back up the original files before replacing them.

### Method B: Ask Codex to Reimplement the Guide

Give this guide to Codex and ask it to apply and verify each implementation step. This approach is better suited to different VideoLingo versions and reduces conflicts caused by blindly replacing files.

## Implementation Steps

### 1. Add Validation Scripts

Add:

```text
scripts/validate_local.py
scripts/run_regression_checks.py
```

At minimum, the validation scripts should confirm that:

- Critical Python files compile.
- `translations/en.json` and `translations/zh-CN.json` contain valid JSON.
- Short subtitle-fragment merging behaves correctly.
- Spacing between Chinese and English text or abbreviations is correct, for example `工作流模型 API 密钥有效`.
- Abnormally long `Thank you` timestamps are trimmed instead of extending the entire subtitle.

Run:

```bash
python scripts/validate_local.py
python scripts/run_regression_checks.py
```

### 2. Separate the Upload-Copy Module

Add:

```text
core/st_utils/upload_copy.py
```

Responsibilities:

- Automatically read the latest bilingual subtitle file:
  - `*_trans_src.srt`
  - `*_src_trans.srt`
- Use the latest bilingual subtitles as the primary source.
- Treat the original video title and description only as supporting context.
- Generate Chinese-only upload copy containing:
  - The original title.
  - The original description.
  - Ten Chinese title candidates.
  - Ten Chinese description candidates.
- Keep Chinese titles at approximately 15 Chinese characters.
- Keep Chinese descriptions at approximately 100 Chinese characters.
- Bind the cache to a hash of the subtitle content so it is invalidated automatically after subtitle changes.

Keep only this import in `st.py`:

```python
from core.st_utils.upload_copy import render_upload_copy_suggestions
```

Call it after subtitle generation or video merging:

```python
render_upload_copy_suggestions(_is_task_running)
```

### 3. Separate the Task-State Module

Add:

```text
core/st_utils/task_state.py
```

It is responsible for:

- `output/.videolingo_task.lock`
- `output/.videolingo_task_status.json`
- Determining whether a task is still running.
- Unlocking automatically after a page refresh or interrupted Streamlit rerun.
- Reading and writing failed, stopped, and completed states.

Keep the progress UI and task-guard logic in `st.py`, but move the underlying state operations into `task_state.py`.

### 4. Introduce Dual-Model Routing

Add:

```text
core/utils/model_router.py
```

Model roles:

- `workflow`: summaries, terminology, structured JSON workflows, reflection, ambiguity review, and upload copy.
- `translator`: plain-text subtitle translation.

Configuration source:

```yaml
api:
  key: ''
  base_url: ''
  model: ''
  llm_support_json: true

translator_api:
  key: 'sk-local'
  base_url: 'http://127.0.0.1:8765/v1'
  model: 'hy-mt2-7b'
  llm_support_json: false
  temperature: 0.2
  max_tokens: 256
```

`core/utils/ask_gpt.py` should continue to expose the original API:

```python
ask_gpt(prompt, resp_type=None, valid_def=None, log_title="default", api_role="workflow")
list_available_models(api_role="workflow")
```

Internally, however, it should route requests to the workflow or translation model through `ModelRouter`.

### 5. Add a Local-Translation Refinement Toggle

Add this setting to `config.yaml`:

```yaml
translator_refine_with_workflow: true
```

Add a toggle to the translation-model section of the GUI:

```text
Refine local translation results
```

Behavior:

- Enabled: the local translation model translates first, then the workflow LLM reflects on and refines the result.
- Disabled: use the local translation-model output directly, with an optional ambiguity check only.
- If workflow refinement fails, do not stop the entire task; fall back to the local translation result.

### 6. Preserve and Strengthen Subtitle-Quality Rules

Important rules:

- As a general rule, do not split short English sentences containing fewer than ten words.
- Merge English fragments that are too short so a sentence is not divided excessively.
- Remove obvious filler words such as `um` and `uh`.
- Correct common capitalization and standard spellings, including:
  - The pronoun `I`.
  - `iPhone`.
  - `AI`, `NBA`, `DNA`, and `MBA`.
- Preserve spaces between Chinese text and English words, abbreviations, or numbers, for example:
  - `工作流模型 API 密钥有效`
  - `iPhone 手机`
  - `AI 技术`
- Detect and trim abnormally long word-level timestamps, especially `Thank you` segments caused by WhisperX hallucinations or misalignment.

Keep or add:

```text
core/spacy_utils/merge_short_segments.py
core/utils/text_normalize.py
```

### 7. Optimize Caching and Configuration Reads

In `core/utils/config_utils.py`:

- Cache `config.yaml` in memory based on its modification time.
- Explicitly invalidate the cache after the GUI updates a setting.

In `core/utils/ask_gpt.py`:

- Write GPT logs through a temporary file followed by an atomic `os.replace`.
- Fall back to an empty list when a damaged log cannot be read.
- Include `api_role` in cache keys so workflow and translation models never share cached results accidentally.

### 8. Add a History Manifest

Create `manifest.json` during project archiving.

Recommended content:

```json
{
  "generated_at": "YYYY-MM-DD HH:MM:SS",
  "source_video": "xxx.mp4",
  "language": {
    "source": "en",
    "target": "简体中文"
  },
  "workflow_model": {
    "base_url": "...",
    "model": "...",
    "llm_support_json": true
  },
  "translator_model": {
    "base_url": "...",
    "model": "...",
    "llm_support_json": false
  },
  "settings": {
    "burn_subtitles": true,
    "reflect_translate": true,
    "translator_refine_with_workflow": true,
    "enable_ambiguity_check": false,
    "translation_max_workers": 4
  },
  "files": []
}
```

Do not include API keys.

### 9. Update `.gitignore`

Confirm that the following are ignored:

```gitignore
/output/
/history/
_model_cache/
config_history.json
streamlit.log
streamlit.pid
*.bac.py
*.backup.py
.DS_Store
__pycache__/
*.py[cod]
```

## Recommended Configuration

### Local Translation Model

If the translation model is exposed through a local llama.cpp, LM Studio, or Ollama OpenAI-compatible API:

```yaml
translator_api:
  key: 'sk-local'
  base_url: 'http://127.0.0.1:8765/v1'
  model: 'hy-mt2-7b'
  llm_support_json: false
  temperature: 0.2
  max_tokens: 256
translation_max_workers: 4
```

If the local model blocks or fails under concurrency, reduce the worker count:

```yaml
translation_max_workers: 1
```

### Workflow Model

Use a local or remote model with reliable JSON support as the workflow model:

```yaml
api:
  key: '<your-api-key>'
  base_url: 'https://api.example.com/v1'
  model: '<workflow-model>'
  llm_support_json: true
```

## Verification Checklist

Run the following after every migration:

```bash
python scripts/validate_local.py
python scripts/run_regression_checks.py
streamlit run st.py
```

Confirm in the GUI that:

- The page contains no `Traceback`.
- The LLM configuration displays both the workflow model and the translation model.
- The `Refine local translation results` toggle is visible.
- The ambiguity-review report appears after subtitle generation.
- Video merging can continue after the review is confirmed.
- The merged-video preview is displayed.
- Upload-copy suggestions are available.

## Troubleshooting

### The Page Says a Task Is Already Running, but the Terminal Has No Logs

Check:

```text
output/.videolingo_task.lock
output/.videolingo_task_status.json
```

The optimized task-state layer should unlock automatically when the process no longer exists or a page refresh interrupted it, then allow processing to continue from the failed step.

### `Too many open files`

First reduce:

```yaml
translation_max_workers: 1
```

Also confirm that the optimized versions of these files are in use:

```text
core/utils/ask_gpt.py
core/utils/config_utils.py
```

### Upload Copy Is Not Based on the Latest Subtitles

Confirm that the latest subtitle file exists:

```text
*_trans_src.srt
*_src_trans.srt
```

The upload-copy cache is tied to the subtitle hash. If the subtitles have changed but the page still shows old copy, click:

```text
Regenerate upload-copy suggestions
```

## Final Acceptance Criteria

- A local translation model can produce the initial subtitle translation.
- A workflow LLM can generate summaries, terminology, reflection, ambiguity review, and upload copy.
- Subtitle review takes place before video merging.
- After bilingual subtitles are edited, video merging uses the latest subtitle files.
- History archives contain `manifest.json`.
- All validation scripts pass.
