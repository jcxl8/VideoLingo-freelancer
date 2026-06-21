<div align="center">

# VideoLingo-Freelancer

本地视频翻译、字幕制作与配音工作台

[English](../README.md)｜**简体中文**｜[Español](README.es.md)｜[Русский](README.ru.md)｜[Français](README.fr.md)｜[Deutsch](README.de.md)｜[Italiano](README.it.md)｜[日本語](README.ja.md)

</div>

## 简介

VideoLingo-Freelancer 是基于 [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) 定制的本地视频译制工具，面向自由职业者和独立创作者。它将本地 ASR、双模型翻译、字幕校对、横竖屏排版、任务恢复、历史项目和配音整合在一个 Streamlit 工作台中。

## 主要功能

- Apple Silicon 使用 MLX Whisper，其他支持平台可使用 WhisperX / faster-whisper。
- 支持 8 种界面语言，缺少的定制文案自动回退英文。
- 支持横屏和 9:16 竖屏字幕、双语字幕、硬字幕处理和自定义水印。
- 支持暂停、继续、失败步骤恢复、字幕复核和历史项目重新合成。
- API 密钥可保存在环境变量或不受 Git 跟踪的 `.streamlit/secrets.toml`。

## 安装

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer
python3.12 -m venv .venv
source .venv/bin/activate
python install.py
```

完整安装、配置、限制与验证说明请查看[英文主页](../README.md)。

## 许可证

本项目采用 [Apache License 2.0](../LICENSE)，并保留 VideoLingo 上游归属。本仓库不是上游官方发行版。
