<div align="center">

# VideoLingo-Freelancer

Traduzione video locale, produzione di sottotitoli e doppiaggio

[English](../README.md)｜[简体中文](README.zh.md)｜[Español](README.es.md)｜[Русский](README.ru.md)｜[Français](README.fr.md)｜[Deutsch](README.de.md)｜**Italiano**｜[日本語](README.ja.md)

</div>

## Panoramica

VideoLingo-Freelancer è una distribuzione personalizzata di [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) per freelance e creatori indipendenti. Riunisce ASR locale, traduzione con due modelli, revisione dei sottotitoli, layout orizzontale e verticale, recupero delle attività, cronologia e doppiaggio in Streamlit.

## 🤖 Skill per agenti

Automatizza un’installazione esistente di VideoLingo-Freelancer da **Codex, Claude Code o OpenClaw** con [VideoLingo-Freelancer Skill](https://github.com/jcxl8/videolingo-freelancer-skill). Il suo orchestratore CLI compatibile con AgentSkills prepara gli input, trascrive, traduce, revisiona, renderizza, doppia e archivia i lavori a partire da richieste in linguaggio naturale.

Lo Skill non include il codice sorgente dell’applicazione, i modelli o le credenziali. Installa e configura prima VideoLingo-Freelancer, quindi collega lo Skill all’installazione esistente.

## Funzionalità

- MLX Whisper su Apple Silicon e WhisperX / faster-whisper sugli altri sistemi supportati.
- Otto lingue dell’interfaccia con ripiego sicuro sull’inglese.
- Sottotitoli bilingui per video orizzontali e verticali 9:16, con filigrana personalizzabile.
- Pausa, ripresa, recupero dagli errori e nuova unione dei progetti archiviati.
- Credenziali nelle variabili d’ambiente o in `.streamlit/secrets.toml`, fuori da Git.

## Installazione

Requisiti: Git, FFmpeg/FFprobe disponibili nel `PATH` e un Python di sistema per avviare il bootstrap. uv scarica automaticamente il Python 3.12 mantenuto dal progetto.

Installazione consigliata con uv in un ambiente isolato:

```bash
git clone https://github.com/jcxl8/VideoLingo-freelancer.git
cd VideoLingo-freelancer
python setup_env.py              # usa python3 su macOS/Linux se necessario
```

Per installare senza avviare l’interfaccia, esegui `python setup_env.py --no-launch`. Su Windows puoi poi usare anche `OneKeyStart_uv.bat`.

Alternativa manuale con Python 3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python install.py
```

Installa prima FFmpeg: `brew install ffmpeg` su macOS, `choco install ffmpeg` su Windows oppure `sudo apt install ffmpeg` su Ubuntu/Debian. Apple Silicon installa MLX Whisper tramite dipendenza condizionale; gli altri sistemi configurano PyTorch e WhisperX.

Consulta il [README inglese](../README.md) per configurazione completa, limitazioni e verifiche.

## Licenza

Apache License 2.0. L’attribuzione a VideoLingo è mantenuta; questo repository non è una versione ufficiale upstream.
