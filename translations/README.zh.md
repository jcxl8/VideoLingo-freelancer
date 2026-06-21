<div align="center">

# VideoLingo-Freelancer

本地视频翻译、字幕制作与配音工作台

[English](../README.md)｜**简体中文**｜[Español](README.es.md)｜[Русский](README.ru.md)｜[Français](README.fr.md)｜[Deutsch](README.de.md)｜[Italiano](README.it.md)｜[日本語](README.ja.md)

</div>

## 简介

VideoLingo-Freelancer 是基于 [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) 定制的本地视频译制工具，面向自由职业者和独立创作者。它将本地 ASR、双模型翻译、字幕校对、横竖屏排版、任务恢复、历史项目和配音整合在一个 Streamlit 工作台中。

## 🤖 Agent Skill

通过 [VideoLingo-Freelancer Skill](https://github.com/jcxl8/videolingo-freelancer-skill)，可让 **Codex、Claude Code 或 OpenClaw** 自动操作已经安装好的 VideoLingo-Freelancer。其兼容 AgentSkills 的 CLI 编排器可根据自然语言请求完成输入准备、转录、翻译、校对、字幕烧录、配音和归档。

Skill 不包含本应用源码、模型或密钥。请先安装并配置 VideoLingo-Freelancer，再把 Skill 连接到现有目录。

## 主要功能

- Apple Silicon 使用 MLX Whisper，其他支持平台可使用 WhisperX / faster-whisper。
- 支持 8 种界面语言，缺少的定制文案自动回退英文。
- 支持横屏和 9:16 竖屏字幕、双语字幕、硬字幕处理和自定义水印。
- 支持暂停、继续、失败步骤恢复、字幕复核和历史项目重新合成。
- API 密钥可保存在环境变量或不受 Git 跟踪的 `.streamlit/secrets.toml`。

## 安装

前置条件：Git、系统 `PATH` 中可用的 FFmpeg/FFprobe，以及用于启动引导脚本的 Python。uv 会自动下载本项目维护的 Python 3.12。

推荐使用 uv 创建隔离环境并安装依赖：

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer
python setup_env.py              # macOS/Linux 必要时使用 python3
```

只安装而不启动界面，可运行 `python setup_env.py --no-launch`。Windows 安装完成后也可双击 `OneKeyStart_uv.bat`。

无法使用 uv 时，采用 Python 3.12 手动安装：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python install.py
```

请先安装 FFmpeg，例如 macOS 使用 `brew install ffmpeg`，Windows 使用 `choco install ffmpeg`，Ubuntu/Debian 使用 `sudo apt install ffmpeg`。Apple Silicon 会按条件安装 MLX Whisper；其他平台安装器会配置 PyTorch 与 WhisperX。

完整安装、配置、限制与验证说明请查看[英文主页](../README.md)。

## 许可证

本项目采用 [Apache License 2.0](../LICENSE)，并保留 VideoLingo 上游归属。本仓库不是上游官方发行版。
