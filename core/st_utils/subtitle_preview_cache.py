from pathlib import Path


def ensure_preview(preview_path, renderer):
    """Render a preview only when its content-addressed cache path is missing."""
    path = Path(preview_path)
    if path.is_file():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    renderer()
    return True
