import spacy
from spacy.cli import download
from core.utils import rprint, load_key, except_handler

SPACY_MODEL_MAP = load_key("spacy_model_map")

def get_spacy_model(language: str):
    model = SPACY_MODEL_MAP.get(language.lower(), "en_core_web_md")
    if language not in SPACY_MODEL_MAP:
        rprint(f"[yellow]Spacy model does not support '{language}', using en_core_web_md model as fallback...[/yellow]")
    return model

def check_spacy_model_installed(language=None):
    """Check if the spacy model for the given language is installed. Returns (model_name, is_installed)."""
    if language is None:
        language = "en" if load_key("whisper.language") == "en" else load_key("whisper.detected_language")
    model = get_spacy_model(language)
    try:
        spacy.load(model)
        return model, True
    except Exception:
        return model, False

@except_handler("Failed to load NLP Spacy model")
def init_nlp():
    language = "en" if load_key("whisper.language") == "en" else load_key("whisper.detected_language")
    model = get_spacy_model(language)
    rprint(f"[blue]⏳ Loading NLP Spacy model: <{model}> ...[/blue]")
    try:
        nlp = spacy.load(model)
    except Exception:
        rprint(f"[yellow]Spacy model '{model}' not found. Downloading...[/yellow]")
        try:
            download(model)
            nlp = spacy.load(model)
        except Exception as e:
            rprint(f"[red]❌ Failed to download spacy model '{model}': {e}[/red]")
            rprint(f"[yellow]   Please install manually: python -m spacy download {model}[/yellow]")
            raise
    rprint("[green]✅ NLP Spacy model loaded successfully![/green]")
    return nlp

# --------------------
# define the intermediate files
# --------------------
SPLIT_BY_COMMA_FILE = "output/log/split_by_comma.txt"
SPLIT_BY_CONNECTOR_FILE = "output/log/split_by_connector.txt"
SPLIT_BY_MARK_FILE = "output/log/split_by_mark.txt"
