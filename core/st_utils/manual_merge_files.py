import os
from pathlib import Path


def write_bytes_if_changed(path, content):
    """Write content atomically while preserving mtime when bytes are unchanged."""
    path = Path(path)
    content = bytes(content)
    try:
        if path.is_file() and path.read_bytes() == content:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True
