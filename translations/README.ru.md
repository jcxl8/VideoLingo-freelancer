<div align="center">

# VideoLingo-Freelancer

Локальный перевод видео, создание субтитров и озвучивание

[English](../README.md)｜[简体中文](README.zh.md)｜[Español](README.es.md)｜**Русский**｜[Français](README.fr.md)｜[Deutsch](README.de.md)｜[Italiano](README.it.md)｜[日本語](README.ja.md)

</div>

## Обзор

VideoLingo-Freelancer — адаптированная версия [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) для фрилансеров и независимых авторов. Она объединяет локальное распознавание речи, перевод двумя моделями, проверку субтитров, горизонтальные и вертикальные макеты, восстановление задач, историю проектов и озвучивание.

## 🤖 Навык для агентов

Автоматизируйте установленный VideoLingo-Freelancer из **Codex, Claude Code или OpenClaw** с помощью [VideoLingo-Freelancer Skill](https://github.com/jcxl8/videolingo-freelancer-skill). Совместимый с AgentSkills CLI-оркестратор по запросу на естественном языке подготавливает входные данные, распознаёт речь, переводит, проверяет, встраивает субтитры, озвучивает и архивирует задания.

Skill не содержит исходный код приложения, модели или учётные данные. Сначала установите и настройте VideoLingo-Freelancer, затем подключите Skill к существующей копии.

## Возможности

- MLX Whisper на Apple Silicon и WhisperX / faster-whisper на других поддерживаемых системах.
- Восемь языков интерфейса с безопасным возвратом к английскому.
- Двуязычные субтитры для горизонтального и вертикального видео 9:16, настраиваемый водяной знак.
- Пауза, продолжение, восстановление после ошибки и повторная сборка архивных проектов.
- Секреты в переменных окружения или `.streamlit/secrets.toml`, вне Git.

## Установка

Требования: Git, FFmpeg/FFprobe в `PATH` и системный Python для запуска установщика. uv автоматически загрузит поддерживаемый проектом Python 3.12.

Рекомендуемая установка через uv в изолированное окружение:

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer
python setup_env.py              # при необходимости используйте python3 в macOS/Linux
```

Для установки без запуска интерфейса выполните `python setup_env.py --no-launch`. После установки в Windows также доступен `OneKeyStart_uv.bat`.

Ручной вариант с Python 3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python install.py
```

Сначала установите FFmpeg: `brew install ffmpeg` в macOS, `choco install ffmpeg` в Windows или `sudo apt install ffmpeg` в Ubuntu/Debian. На Apple Silicon условная зависимость устанавливает MLX Whisper; на других системах установщик настраивает PyTorch и WhisperX.

Полные инструкции по настройке и ограничениям находятся в [английском README](../README.md).

## Лицензия

Apache License 2.0. Сохранена атрибуция VideoLingo; это не официальный выпуск исходного проекта.
