<div align="center">

# VideoLingo-Freelancer

Lokale Videoübersetzung, Untertitelproduktion und Synchronisation

[English](../README.md)｜[简体中文](README.zh.md)｜[Español](README.es.md)｜[Русский](README.ru.md)｜[Français](README.fr.md)｜**Deutsch**｜[Italiano](README.it.md)｜[日本語](README.ja.md)

</div>

## Überblick

VideoLingo-Freelancer ist eine angepasste Distribution von [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) für Freelancer und unabhängige Kreative. Sie verbindet lokale Spracherkennung, Übersetzung mit zwei Modellen, Untertitelprüfung, Quer- und Hochformat, Aufgabenwiederherstellung, Projektverlauf und Synchronisation in Streamlit.

## 🤖 Agent Skill

Automatisiere eine vorhandene VideoLingo-Freelancer-Installation aus **Codex, Claude Code oder OpenClaw** mit dem [VideoLingo-Freelancer Skill](https://github.com/jcxl8/videolingo-freelancer-skill). Der AgentSkills-kompatible CLI-Orchestrator bereitet Eingaben vor, transkribiert, übersetzt, prüft, rendert, synchronisiert und archiviert Aufträge anhand natürlichsprachiger Anweisungen.

Der Skill enthält weder den Quellcode dieser Anwendung noch Modelle oder Zugangsdaten. Installiere und konfiguriere zuerst VideoLingo-Freelancer und verbinde den Skill anschließend mit dieser Installation.

## Hauptfunktionen

- MLX Whisper auf Apple Silicon und WhisperX / faster-whisper auf anderen unterstützten Systemen.
- Acht Oberflächensprachen mit sicherem Rückgriff auf Englisch.
- Zweisprachige Untertitel für Querformat und 9:16-Hochformat sowie anpassbare Wasserzeichen.
- Pausieren, Fortsetzen, Fehlerwiederherstellung und erneutes Zusammenführen archivierter Projekte.
- Zugangsdaten in Umgebungsvariablen oder `.streamlit/secrets.toml`, nicht in Git.

## Installation

Voraussetzungen: Git, FFmpeg/FFprobe im `PATH` und ein System-Python zum Starten des Bootstrap-Skripts. uv lädt das vom Projekt gepflegte Python 3.12 automatisch herunter.

Empfohlene Installation mit uv in einer isolierten Umgebung:

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer
python setup_env.py              # unter macOS/Linux bei Bedarf python3 verwenden
```

Mit `python setup_env.py --no-launch` wird nur installiert, ohne die Oberfläche zu starten. Unter Windows kann die Anwendung danach auch mit `OneKeyStart_uv.bat` gestartet werden.

Manuelle Alternative mit Python 3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python install.py
```

Installiere zuerst FFmpeg: `brew install ffmpeg` unter macOS, `choco install ffmpeg` unter Windows oder `sudo apt install ffmpeg` unter Ubuntu/Debian. Auf Apple Silicon wird MLX Whisper bedingt installiert; andere Systeme konfigurieren PyTorch und WhisperX.

Vollständige Hinweise zu Konfiguration, Einschränkungen und Tests stehen im [englischen README](../README.md).

## Lizenz

Apache License 2.0. Die VideoLingo-Zuordnung bleibt erhalten; dieses Repository ist keine offizielle Upstream-Version.
