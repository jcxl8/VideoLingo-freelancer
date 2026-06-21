<div align="center">

# VideoLingo-Freelancer

Traducción local de vídeo, producción de subtítulos y doblaje

[English](../README.md)｜[简体中文](README.zh.md)｜**Español**｜[Русский](README.ru.md)｜[Français](README.fr.md)｜[Deutsch](README.de.md)｜[Italiano](README.it.md)｜[日本語](README.ja.md)

</div>

## Descripción

VideoLingo-Freelancer es una distribución personalizada de [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) para profesionales independientes y creadores. Reúne ASR local, traducción con dos modelos, revisión de subtítulos, diseños horizontal y vertical, recuperación de tareas, historial y doblaje en Streamlit.

## 🤖 Skill para agentes

Automatiza una instalación existente de VideoLingo-Freelancer desde **Codex, Claude Code u OpenClaw** con [VideoLingo-Freelancer Skill](https://github.com/jcxl8/videolingo-freelancer-skill). Su orquestador CLI compatible con AgentSkills prepara entradas, transcribe, traduce, revisa, renderiza, dobla y archiva trabajos a partir de solicitudes en lenguaje natural.

El Skill no incluye el código fuente de esta aplicación, modelos ni credenciales. Instala y configura primero VideoLingo-Freelancer y después conecta el Skill con esa instalación.

## Funciones principales

- MLX Whisper en Apple Silicon y WhisperX / faster-whisper en otros sistemas compatibles.
- Ocho idiomas de interfaz con retorno seguro al inglés cuando falta una cadena.
- Subtítulos bilingües para vídeo horizontal y vertical 9:16, además de marca de agua personalizable.
- Pausa, reanudación, recuperación desde errores y reutilización de proyectos archivados.
- Credenciales en variables de entorno o `.streamlit/secrets.toml`, fuera de Git.

## Instalación

Requisitos: Git, FFmpeg/FFprobe disponibles en `PATH` y un Python del sistema para iniciar el instalador. uv descargará automáticamente el Python 3.12 mantenido por el proyecto.

Instalación recomendada con uv y un entorno aislado:

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer
python setup_env.py              # use python3 en macOS/Linux si es necesario
```

Para instalar sin abrir la interfaz, ejecuta `python setup_env.py --no-launch`. En Windows también puedes usar `OneKeyStart_uv.bat` después de la instalación.

Alternativa manual con Python 3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python install.py
```

Instala primero FFmpeg: `brew install ffmpeg` en macOS, `choco install ffmpeg` en Windows o `sudo apt install ffmpeg` en Ubuntu/Debian. Apple Silicon instala MLX Whisper mediante una dependencia condicional; los demás sistemas configuran PyTorch y WhisperX.

Consulta la [documentación completa en inglés](../README.md) para configuración, limitaciones y validación.

## Licencia

Apache License 2.0. Este proyecto conserva la atribución a VideoLingo y no es una versión oficial del proyecto original.
