<div align="center">

# VideoLingo-Freelancer

Traduction vidéo locale, production de sous-titres et doublage

[English](../README.md)｜[简体中文](README.zh.md)｜[Español](README.es.md)｜[Русский](README.ru.md)｜**Français**｜[Deutsch](README.de.md)｜[Italiano](README.it.md)｜[日本語](README.ja.md)

</div>

## Présentation

VideoLingo-Freelancer est une distribution personnalisée de [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo), destinée aux indépendants et aux créateurs. Elle regroupe ASR local, traduction à deux modèles, contrôle des sous-titres, formats paysage et vertical, reprise des tâches, historique et doublage dans Streamlit.

## 🤖 Skill pour agents

Automatisez une installation existante de VideoLingo-Freelancer depuis **Codex, Claude Code ou OpenClaw** avec le [VideoLingo-Freelancer Skill](https://github.com/jcxl8/videolingo-freelancer-skill). Son orchestrateur CLI compatible AgentSkills prépare les entrées, transcrit, traduit, contrôle, incruste les sous-titres, double et archive les tâches à partir de demandes en langage naturel.

Le Skill n’inclut ni le code source de cette application, ni les modèles, ni les identifiants. Installez et configurez d’abord VideoLingo-Freelancer, puis connectez le Skill à cette installation.

## Fonctionnalités

- MLX Whisper sur Apple Silicon et WhisperX / faster-whisper sur les autres systèmes compatibles.
- Huit langues d’interface avec repli automatique vers l’anglais.
- Sous-titres bilingues pour les vidéos paysage et verticales 9:16, filigrane personnalisable.
- Pause, reprise, récupération après erreur et remontage des projets archivés.
- Identifiants dans les variables d’environnement ou `.streamlit/secrets.toml`, hors de Git.

## Installation

Prérequis : Git, FFmpeg/FFprobe accessibles dans le `PATH` et un Python système pour lancer l’amorçage. uv télécharge automatiquement le Python 3.12 maintenu par le projet.

Installation recommandée avec uv dans un environnement isolé :

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer
python setup_env.py              # utilisez python3 sur macOS/Linux si nécessaire
```

Pour installer sans ouvrir l’interface, exécutez `python setup_env.py --no-launch`. Sous Windows, `OneKeyStart_uv.bat` permet ensuite de démarrer l’application.

Alternative manuelle avec Python 3.12 :

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python install.py
```

Installez d’abord FFmpeg : `brew install ffmpeg` sous macOS, `choco install ffmpeg` sous Windows ou `sudo apt install ffmpeg` sous Ubuntu/Debian. Apple Silicon installe MLX Whisper par dépendance conditionnelle ; les autres systèmes configurent PyTorch et WhisperX.

Consultez le [README anglais](../README.md) pour la configuration complète, les limites et la validation.

## Licence

Apache License 2.0. L’attribution à VideoLingo est conservée ; ce dépôt n’est pas une version officielle du projet amont.
