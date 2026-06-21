import json
import os
import tempfile
from pathlib import Path


def atomic_write_text(path, text, *, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(str(text))
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, path)
        os.chmod(path, mode)
    finally:
        if os.path.exists(temporary_name):
            os.remove(temporary_name)


def atomic_write_json(path, data, *, mode=0o600, indent=None):
    atomic_write_text(
        path,
        json.dumps(data, ensure_ascii=False, indent=indent),
        mode=mode,
    )
