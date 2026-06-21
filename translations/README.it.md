<div align="center">

# VideoLingo-Freelancer

Traduzione video locale, produzione di sottotitoli e doppiaggio

[English](../README.md)｜[简体中文](README.zh.md)｜[Español](README.es.md)｜[Русский](README.ru.md)｜[Français](README.fr.md)｜[Deutsch](README.de.md)｜**Italiano**｜[日本語](README.ja.md)

</div>

## Panoramica

VideoLingo-Freelancer è una distribuzione personalizzata di [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) per freelance e creatori indipendenti. Riunisce ASR locale, traduzione con due modelli, revisione dei sottotitoli, layout orizzontale e verticale, recupero delle attività, cronologia e doppiaggio in Streamlit.

## Funzionalità

- MLX Whisper su Apple Silicon e WhisperX / faster-whisper sugli altri sistemi supportati.
- Otto lingue dell’interfaccia con ripiego sicuro sull’inglese.
- Sottotitoli bilingui per video orizzontali e verticali 9:16, con filigrana personalizzabile.
- Pausa, ripresa, recupero dagli errori e nuova unione dei progetti archiviati.
- Credenziali nelle variabili d’ambiente o in `.streamlit/secrets.toml`, fuori da Git.

## Installazione

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer
python3.12 -m venv .venv
source .venv/bin/activate
python install.py
```

Consulta il [README inglese](../README.md) per configurazione completa, limitazioni e verifiche.

## Licenza

Apache License 2.0. L’attribuzione a VideoLingo è mantenuta; questo repository non è una versione ufficiale upstream.
