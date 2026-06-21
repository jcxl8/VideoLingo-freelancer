<div align="center">

# VideoLingo-Freelancer

Traducción local de vídeo, producción de subtítulos y doblaje

[English](../README.md)｜[简体中文](README.zh.md)｜**Español**｜[Русский](README.ru.md)｜[Français](README.fr.md)｜[Deutsch](README.de.md)｜[Italiano](README.it.md)｜[日本語](README.ja.md)

</div>

## Descripción

VideoLingo-Freelancer es una distribución personalizada de [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) para profesionales independientes y creadores. Reúne ASR local, traducción con dos modelos, revisión de subtítulos, diseños horizontal y vertical, recuperación de tareas, historial y doblaje en Streamlit.

## Funciones principales

- MLX Whisper en Apple Silicon y WhisperX / faster-whisper en otros sistemas compatibles.
- Ocho idiomas de interfaz con retorno seguro al inglés cuando falta una cadena.
- Subtítulos bilingües para vídeo horizontal y vertical 9:16, además de marca de agua personalizable.
- Pausa, reanudación, recuperación desde errores y reutilización de proyectos archivados.
- Credenciales en variables de entorno o `.streamlit/secrets.toml`, fuera de Git.

## Instalación

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer
python3.12 -m venv .venv
source .venv/bin/activate
python install.py
```

Consulta la [documentación completa en inglés](../README.md) para configuración, limitaciones y validación.

## Licencia

Apache License 2.0. Este proyecto conserva la atribución a VideoLingo y no es una versión oficial del proyecto original.
