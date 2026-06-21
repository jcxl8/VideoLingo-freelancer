# VideoLingo 本地双模型优化迁移指南

本文档用于在其他电脑上复现本机 VideoLingo 的本地化优化流程。目标是把 VideoLingo 改造成适合“本地翻译模型 + 工作流大语言模型”的视频译制工作台。

## 目标

- 使用本地翻译模型接口负责字幕翻译，例如 Hy-MT、TranslateGemma、llama.cpp server、LM Studio 或 Ollama 兼容接口。
- 使用工作流大语言模型负责摘要、术语抽取、反思润色、歧义核查、字幕质量审校、上传标题和简介生成。
- 保留人工核查闭环：字幕生成后先显示歧义报告，确认后再合并视频。
- 支持手动合并字幕和视频、字幕样式预览、合并后视频预览、历史项目归档。
- 提升可维护性：拆分 GUI、任务状态、模型路由、上传文案模块。

## 适用环境

- macOS 或 Linux。
- Python 环境已能运行 VideoLingo。
- 已有本地或远程 OpenAI-compatible API：
  - 工作流模型：支持 JSON 输出更好。
  - 翻译模型：可以是本机 `http://127.0.0.1:xxxx/v1`。
- 已安装 FFmpeg。
- 如使用 WhisperX 本地模式，需确认对应模型和依赖可用。

## 不要迁移的内容

不要直接复制以下敏感或机器相关内容：

- `config.yaml` 里的真实 API 密钥。
- YouTube cookies 文件路径。
- `config_history.json`。
- `output/`、`history/`、`_model_cache/`。
- `streamlit.log`、`streamlit.pid`。

迁移到新电脑后，应在 GUI 里重新填写 API 密钥、BASE_URL、模型名和 cookies。

## 推荐迁移方式

### 方式 A：复制已优化文件

从已优化电脑复制以下文件到新电脑同名位置：

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

如果新电脑是干净上游 VideoLingo，建议先备份原文件再覆盖。

### 方式 B：让 Codex 按本指南重新实施

把本文档交给 Codex，并要求按“实施步骤”逐步修改和验证。适合不同版本 VideoLingo，能减少直接覆盖造成的冲突。

## 实施步骤

### 1. 建立验证脚本

新增：

```text
scripts/validate_local.py
scripts/run_regression_checks.py
```

验证脚本应至少检查：

- 关键 Python 文件能编译。
- `translations/en.json` 和 `translations/zh-CN.json` 是合法 JSON。
- 短字幕碎片合并规则正常。
- 中英文/缩写间空格正常，例如 `工作流模型 API 密钥有效`。
- 异常长 `Thank you` 时间戳能被修剪，不再拖长整条字幕。

运行：

```bash
python scripts/validate_local.py
python scripts/run_regression_checks.py
```

### 2. 拆分上传文案模块

新增：

```text
core/st_utils/upload_copy.py
```

功能：

- 自动读取最新双语字幕文件：
  - `*_trans_src.srt`
  - `*_src_trans.srt`
- 以最新双语字幕为主要依据。
- 原视频标题和视频简介只作为辅助背景。
- 生成中文-only 上传文案：
  - 原标题
  - 原简介
  - 10 个中文标题候选
  - 10 个中文简介候选
- 中文标题约 15 个汉字。
- 中文简介约 100 个汉字。
- 缓存需绑定字幕内容 hash，字幕更新后自动失效。

在 `st.py` 中只保留调用：

```python
from core.st_utils.upload_copy import render_upload_copy_suggestions
```

并在字幕生成完成或合并完成后调用：

```python
render_upload_copy_suggestions(_is_task_running)
```

### 3. 拆分任务状态模块

新增：

```text
core/st_utils/task_state.py
```

负责：

- `output/.videolingo_task.lock`
- `output/.videolingo_task_status.json`
- 判断任务是否仍在运行。
- 页面刷新或 Streamlit rerun 后自动解锁。
- 失败、终止、完成状态读写。

`st.py` 中保留进度 UI 和任务保护逻辑，但底层读写应调用 `task_state.py`。

### 4. 抽象双模型路由

新增：

```text
core/utils/model_router.py
```

模型角色：

- `workflow`：摘要、术语、JSON 流程、反思、歧义、上传文案。
- `translator`：纯文本字幕翻译。

配置来源：

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

`core/utils/ask_gpt.py` 应继续暴露原接口：

```python
ask_gpt(prompt, resp_type=None, valid_def=None, log_title="default", api_role="workflow")
list_available_models(api_role="workflow")
```

但内部通过 `ModelRouter` 路由到工作流模型或翻译模型。

### 5. 增加本地翻译结果润色开关

在 `config.yaml` 中新增：

```yaml
translator_refine_with_workflow: true
```

在 GUI 的翻译模型设置区域新增开关：

```text
润色本地翻译结果
```

逻辑：

- 开启：本地翻译模型先翻译，工作流大模型再反思润色。
- 关闭：本地翻译模型直接输出，最多做歧义核查。
- 工作流润色失败时，不应中断整个任务，应退回本地翻译结果。

### 6. 保留并加强字幕质量规则

重点规则：

- 少于 10 个英文词的短句原则上不切分。
- 合并过短英文碎片，避免一句话被切得太碎。
- 去除明显语气词，如 `um`、`uh`。
- 修复常见大小写和规范写法，例如：
  - 主语 `I`
  - `iPhone`
  - `AI`、`NBA`、`DNA`、`MBA`
- 中文和英文/缩写/数字之间保留空格，例如：
  - `工作流模型 API 密钥有效`
  - `iPhone 手机`
  - `AI 技术`
- 检测并修剪异常长的词级时间戳，尤其是 WhisperX 幻觉或错位造成的 `Thank you`。

建议保留或新增：

```text
core/spacy_utils/merge_short_segments.py
core/utils/text_normalize.py
```

### 7. 优化缓存和配置读取

`core/utils/config_utils.py`：

- 对 `config.yaml` 做按 mtime 的内存缓存。
- GUI 更新配置后主动失效缓存。

`core/utils/ask_gpt.py`：

- GPT 日志写入使用临时文件 + `os.replace` 原子替换。
- 读取损坏日志时回退为空列表。
- 缓存 key 应区分 `api_role`，避免工作流模型和翻译模型串缓存。

### 8. 增加 History manifest

在归档函数中新增 `manifest.json`。

建议内容：

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

不要写入 API key。

### 9. 更新 `.gitignore`

确认忽略：

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

## 推荐配置

### 本机翻译模型

如果翻译模型是本机 llama.cpp / LM Studio / Ollama 兼容 OpenAI API：

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

如果本地模型容易阻塞或报错，可把并发降为：

```yaml
translation_max_workers: 1
```

### 工作流模型

工作流模型建议使用支持 JSON 的远程或本地大模型：

```yaml
api:
  key: '<your-api-key>'
  base_url: 'https://api.example.com/v1'
  model: '<workflow-model>'
  llm_support_json: true
```

## 验证清单

每次迁移后执行：

```bash
python scripts/validate_local.py
python scripts/run_regression_checks.py
streamlit run st.py
```

在 GUI 中确认：

- 页面无 `Traceback`。
- LLM 配置能显示工作流模型和翻译模型。
- 能看到 `润色本地翻译结果` 开关。
- 字幕生成完成后能看到歧义核查报告。
- 核查确认后能继续合并视频。
- 合并后能看到视频预览。
- 能看到上传文案建议。

## 常见问题

### 页面提示已有任务运行，但终端没有日志

检查：

```text
output/.videolingo_task.lock
output/.videolingo_task_status.json
```

优化后的任务状态层应在进程不存在或页面刷新中断后自动解锁，并允许从失败步骤继续。

### 出现 Too many open files

优先降低：

```yaml
translation_max_workers: 1
```

并确认已使用优化后的：

```text
core/utils/ask_gpt.py
core/utils/config_utils.py
```

### 上传文案不是根据最新字幕生成

确认最新字幕文件存在：

```text
*_trans_src.srt
*_src_trans.srt
```

上传文案缓存会绑定字幕 hash。如果字幕已修改但页面仍旧，点击：

```text
重新生成上传文案建议
```

## 最终验收标准

- 可以使用本地翻译模型完成字幕初译。
- 可以使用工作流大模型完成摘要、术语、反思、歧义和上传文案。
- 字幕生成后先核查，再合并视频。
- 修改双语字幕后，合并视频使用最新字幕。
- 历史归档包含 `manifest.json`。
- 验证脚本全部通过。
