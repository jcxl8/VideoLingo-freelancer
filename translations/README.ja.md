<div align="center">

# VideoLingo-Freelancer

ローカル動画翻訳・字幕制作・吹き替えワークスペース

[English](../README.md)｜[简体中文](README.zh.md)｜[Español](README.es.md)｜[Русский](README.ru.md)｜[Français](README.fr.md)｜[Deutsch](README.de.md)｜[Italiano](README.it.md)｜**日本語**

</div>

## 概要

VideoLingo-Freelancer は、フリーランサーと個人クリエイター向けに [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) をカスタマイズした配布版です。ローカル ASR、2 モデル翻訳、字幕校正、横長・縦長レイアウト、タスク復旧、履歴、吹き替えを Streamlit に統合します。

## 主な機能

- Apple Silicon では MLX Whisper、その他の対応環境では WhisperX / faster-whisper を利用できます。
- 8 種類の UI 言語を選択でき、未翻訳の項目は安全に英語へフォールバックします。
- 横長動画と 9:16 縦長動画のバイリンガル字幕、ハード字幕処理、カスタム透かしに対応します。
- 一時停止、再開、失敗地点からの復旧、履歴プロジェクトの再結合に対応します。
- 認証情報は環境変数または Git 対象外の `.streamlit/secrets.toml` に保存できます。

## インストール

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer
python3.12 -m venv .venv
source .venv/bin/activate
python install.py
```

設定、制限、検証方法の詳細は[英語版 README](../README.md)を参照してください。

## ライセンス

Apache License 2.0。VideoLingo への帰属を保持しており、本リポジトリは上流の公式リリースではありません。
