<div align="center">

# VideoLingo-Freelancer

Локальный перевод видео, создание субтитров и озвучивание

[English](../README.md)｜[简体中文](README.zh.md)｜[Español](README.es.md)｜**Русский**｜[Français](README.fr.md)｜[Deutsch](README.de.md)｜[Italiano](README.it.md)｜[日本語](README.ja.md)

</div>

## Обзор

VideoLingo-Freelancer — адаптированная версия [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) для фрилансеров и независимых авторов. Она объединяет локальное распознавание речи, перевод двумя моделями, проверку субтитров, горизонтальные и вертикальные макеты, восстановление задач, историю проектов и озвучивание.

## Возможности

- MLX Whisper на Apple Silicon и WhisperX / faster-whisper на других поддерживаемых системах.
- Восемь языков интерфейса с безопасным возвратом к английскому.
- Двуязычные субтитры для горизонтального и вертикального видео 9:16, настраиваемый водяной знак.
- Пауза, продолжение, восстановление после ошибки и повторная сборка архивных проектов.
- Секреты в переменных окружения или `.streamlit/secrets.toml`, вне Git.

## Установка

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer
python3.12 -m venv .venv
source .venv/bin/activate
python install.py
```

Полные инструкции по настройке и ограничениям находятся в [английском README](../README.md).

## Лицензия

Apache License 2.0. Сохранена атрибуция VideoLingo; это не официальный выпуск исходного проекта.
