import json
import os
import re
from pathlib import Path


_GENERATED_VIDEO_SUFFIX = re.compile(
    r"(?:_sub|_dub)(?:_v\d+)?$",
    re.IGNORECASE,
)


def is_generated_video(filename):
    stem = Path(filename).stem
    return bool(
        stem.startswith(("output_", "manual_"))
        or stem in ("output_sub", "output_dub")
        or _GENERATED_VIDEO_SUFFIX.search(stem)
        or "_sub_backup" in stem
        or "_dub_backup" in stem
    )


def _manifest_source_name(project_dir):
    project_dir = Path(project_dir)
    manifest_path = project_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source_video = manifest.get("source_video")
        if source_video:
            return Path(source_video).name
    except (OSError, ValueError, TypeError):
        pass

    job_manifest_path = project_dir / "job_manifest.json"
    try:
        job_manifest = json.loads(job_manifest_path.read_text(encoding="utf-8"))
        source_video = job_manifest.get("input", {}).get("path")
        if source_video:
            return Path(source_video).name
    except (OSError, ValueError, TypeError):
        pass
    return None


def find_project_original_videos(project_dir, allowed_exts):
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        return []
    allowed_exts = tuple(str(ext).lower() for ext in allowed_exts)
    source_name = _manifest_source_name(project_dir)
    if source_name:
        source_path = project_dir / source_name
        if source_path.is_file() and source_path.suffix.lower() in allowed_exts:
            return [str(source_path)]

    originals = [
        path
        for path in project_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in allowed_exts
        and not is_generated_video(path.name)
    ]
    return [str(path) for path in sorted(originals, key=os.path.getmtime, reverse=True)]
