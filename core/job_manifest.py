import hashlib
import json
import os
import time
from pathlib import Path

from core.utils.atomic_files import atomic_write_json


DEFAULT_JOB_MANIFEST = "output/job_manifest.json"
MANIFEST_VERSION = 1


def file_fingerprint(path):
    resolved = Path(path).expanduser().resolve()
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def load_job_manifest(path=DEFAULT_JOB_MANIFEST):
    manifest = Path(path)
    if not manifest.exists():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != MANIFEST_VERSION:
            return None
        return data
    except (OSError, UnicodeError, json.JSONDecodeError):
        corrupt = manifest.with_name(f"{manifest.name}.corrupt-{time.time_ns()}")
        try:
            os.replace(manifest, corrupt)
        except OSError:
            pass
        return None


def manifest_input_video(path=DEFAULT_JOB_MANIFEST):
    data = load_job_manifest(path)
    fingerprint = data.get("input") if data else None
    if not isinstance(fingerprint, dict) or not fingerprint.get("path"):
        return None
    try:
        current = file_fingerprint(fingerprint["path"])
    except OSError:
        return None
    return current["path"] if current == fingerprint else None


def record_subtitle_merge(
    *,
    video_file,
    output_video,
    src_srt=None,
    trans_srt=None,
    subtitle_mode,
    manifest_path=DEFAULT_JOB_MANIFEST,
):
    settings = {"subtitle_mode": subtitle_mode}
    config_fingerprint = hashlib.sha256(
        json.dumps(settings, sort_keys=True).encode("utf-8")
    ).hexdigest()
    artifacts = {"video": str(Path(output_video).expanduser().resolve())}
    if src_srt and Path(src_srt).exists():
        artifacts["source_subtitle"] = str(Path(src_srt).expanduser().resolve())
    if trans_srt and Path(trans_srt).exists():
        artifacts["translated_subtitle"] = str(Path(trans_srt).expanduser().resolve())
    data = {
        "version": MANIFEST_VERSION,
        "job_id": hashlib.sha256(
            f"{Path(video_file).resolve()}:{time.time_ns()}".encode("utf-8")
        ).hexdigest()[:16],
        "stage": "subtitle_merge",
        "status": "completed",
        "updated_at_ns": time.time_ns(),
        "input": file_fingerprint(video_file),
        "config_fingerprint": config_fingerprint,
        "settings": settings,
        "artifacts": artifacts,
    }
    atomic_write_json(manifest_path, data, mode=0o600, indent=2)
    return data
