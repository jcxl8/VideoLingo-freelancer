# VideoLingo-Freelancer

面向自由职业者与个人创作者的本地视频译制工作台，支持横屏与竖屏视频的转录、翻译、字幕校对、排版、烧录和配音流程。

本项目基于 [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) 定制开发，并保留上游 Git 历史。感谢 VideoLingo 原作者与贡献者。

> This is a customized VideoLingo distribution for local, creator-oriented video localization. The interface is primarily maintained in Simplified Chinese and English.

## 主要特性

- 本地 ASR：Apple Silicon 可使用 MLX Whisper；其他平台可使用 WhisperX / faster-whisper，模型统一为 Whisper large-v3。
- ASR 语言：自动检测，以及英语、中文、西班牙语、俄语、法语、德语、意大利语、日语。
- 双模型翻译：可将工作流模型与专用翻译模型分开配置，也支持本地 OpenAI 兼容接口。
- 字幕工作流：语义切分、双语字幕、字幕质量检查、歧义复核和选择性重译。
- 横竖屏排版：横屏与 9:16 竖屏使用独立字号、偏移、双语布局和硬字幕策略。
- 自定义水印：支持开关、名称、字号和位置调整。
- 任务恢复：记录步骤状态，可在失败、停止或页面刷新后继续处理。
- 历史项目：归档成片和字幕，并可从历史项目重新合成。
- 本地密钥：敏感配置可存入不受 Git 跟踪的 `.streamlit/secrets.toml`。

## 环境要求

- Python 3.12
- FFmpeg
- macOS Apple Silicon、Windows 或 Linux
- NVIDIA GPU 并非必需；长视频在有 GPU 或 Apple Silicon 的电脑上处理更快

模型权重、`output/`、`history/`、`_model_cache/` 和本地密钥不会提交到 Git。

## 安装

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer
python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python install.py
```

`install.py` 会安装依赖并启动 Streamlit。之后可手动启动：

```bash
streamlit run st.py
```

### Apple Silicon 的 MLX Whisper

```bash
pip install mlx-whisper
```

然后在侧边栏将 ASR Runtime 设为 `MLX Whisper / Metal`。非 macOS 平台使用 `WhisperX / faster-whisper`。

## 配置密钥

请勿把真实 API Key 写入公开仓库。应用会优先读取环境变量或 `.streamlit/secrets.toml`，例如：

```toml
VIDEOLINGO_API_KEY = "your-workflow-model-key"
VIDEOLINGO_TRANSLATOR_API_KEY = "your-translation-model-key"
VIDEOLINGO_YOUTUBE_COOKIES_PATH = "/absolute/path/to/cookies.txt"
VIDEOLINGO_AZURE_TTS_API_KEY = "your-tts-key"
```

完整映射见 [`core/utils/secret_store.py`](core/utils/secret_store.py)。`.streamlit/secrets.toml` 已在 `.gitignore` 中排除。

## 验证

```bash
python scripts/check_tracked_secrets.py
python -m compileall -q core scripts st.py
python -m unittest discover -v tests
```

CI 会在每次 push 和 pull request 时执行同类检查。

## 定制说明

- [`LOCAL_OPTIMIZATION_GUIDE.md`](LOCAL_OPTIMIZATION_GUIDE.md)：本地双模型与工作流定制说明
- [`docs/dependency-management.md`](docs/dependency-management.md)：依赖与 CI 环境说明
- [`docs/maintenance/`](docs/maintenance/)：源码边界和维护约定

## 上游与许可证

- Upstream: [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo)
- Customized distribution: [jcxl8/VideoLingo-freelancer](https://github.com/jcxl8/VideoLingo-freelancer)
- License: [Apache License 2.0](LICENSE)

本仓库不是上游项目的官方发行版。发布衍生版本时请继续保留许可证、版权声明和上游归属。
