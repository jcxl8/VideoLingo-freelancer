import os
import torch
from rich.console import Console
from rich import print as rprint
from demucs.pretrained import get_model
from demucs.audio import save_audio, AudioFile
from demucs.apply import apply_model, BagOfModels
from torch.cuda import is_available as is_cuda_available
from typing import Optional
import gc
from core.utils.models import *

def demucs_audio():
    if os.path.exists(_VOCAL_AUDIO_FILE) and os.path.exists(_BACKGROUND_AUDIO_FILE):
        rprint(f"[yellow]⚠️ {_VOCAL_AUDIO_FILE} and {_BACKGROUND_AUDIO_FILE} already exist, skip Demucs processing.[/yellow]")
        return
    
    console = Console()
    os.makedirs(_AUDIO_DIR, exist_ok=True)
    
    console.print("🤖 Loading <htdemucs> model...")
    model = get_model('htdemucs')
    device = "cuda" if is_cuda_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    model.to(device)
    
    console.print("📂 Loading audio file...")
    wav = AudioFile(_RAW_AUDIO_FILE).read(
        streams=0, samplerate=model.samplerate, channels=model.audio_channels
    )
    wav = wav.to(device)
    if wav.dim() == 2:
        wav = wav[None]  # add batch dim
    
    console.print("🎵 Separating audio...")
    with torch.no_grad():
        sources = apply_model(
            model, wav, shifts=1, split=True, overlap=0.25,
            device=device, progress=True
        )
    # sources: tensor (batch, n_sources, channels, length)
    sources = sources[0]  # remove batch dim -> (n_sources, channels, length)
    source_names = list(model.sources)
    vocals_idx = source_names.index('vocals')
    
    kwargs = {"samplerate": model.samplerate, "bitrate": 128, "preset": 2, 
             "clip": "rescale", "as_float": False, "bits_per_sample": 16}
    
    console.print("🎤 Saving vocals track...")
    vocals = sources[vocals_idx]  # (channels, length)
    save_audio(vocals.cpu(), _VOCAL_AUDIO_FILE, **kwargs)
    
    console.print("🎹 Saving background music...")
    background = sum(sources[i] for i in range(len(source_names)) if source_names[i] != 'vocals')
    save_audio(background.cpu(), _BACKGROUND_AUDIO_FILE, **kwargs)
    
    # Clean up memory
    del wav, sources, background, model
    gc.collect()
    if device == 'cuda':
        torch.cuda.empty_cache()
    
    console.print("[green]✨ Audio separation completed![/green]")

if __name__ == "__main__":
    demucs_audio()
