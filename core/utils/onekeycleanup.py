import os
import glob
import json
import time
from core._1_ytdlp import find_video_files
import shutil
from core.utils.config_utils import load_key

def _safe_load_key(key, default=None):
    try:
        return load_key(key)
    except Exception:
        return default

def _relative_files(root_dir):
    files = []
    for path in glob.glob(os.path.join(root_dir, "**", "*"), recursive=True):
        if os.path.isfile(path):
            files.append(os.path.relpath(path, root_dir))
    return sorted(files)

def _write_manifest(video_history_dir, source_video_name):
    manifest = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_video": source_video_name,
        "language": {
            "source": _safe_load_key("whisper.detected_language") or _safe_load_key("whisper.language"),
            "target": _safe_load_key("target_language"),
        },
        "workflow_model": {
            "base_url": _safe_load_key("api.base_url"),
            "model": _safe_load_key("api.model"),
            "llm_support_json": _safe_load_key("api.llm_support_json"),
        },
        "translator_model": {
            "base_url": _safe_load_key("translator_api.base_url"),
            "model": _safe_load_key("translator_api.model"),
            "llm_support_json": _safe_load_key("translator_api.llm_support_json"),
        },
        "settings": {
            "burn_subtitles": _safe_load_key("burn_subtitles"),
            "reflect_translate": _safe_load_key("reflect_translate"),
            "translator_refine_with_workflow": _safe_load_key("translator_refine_with_workflow"),
            "enable_ambiguity_check": _safe_load_key("enable_ambiguity_check"),
            "translation_max_workers": _safe_load_key("translation_max_workers"),
            "subtitle_layout": _safe_load_key("subtitle_layout"),
            "subtitle_layout_profile": _safe_load_key("subtitle_layout_profile"),
            "subtitle_hardsub_strategy": _safe_load_key("subtitle_hardsub_strategy"),
            "hardsub_translation_offset": _safe_load_key("hardsub_translation_offset"),
            "bilingual_translation_offset": _safe_load_key("bilingual_translation_offset"),
            "watermark_enabled": _safe_load_key("watermark_enabled"),
            "watermark_font_size": _safe_load_key("watermark_font_size"),
            "watermark_offset": _safe_load_key("watermark_offset"),
        },
        "files": _relative_files(video_history_dir),
    }
    manifest_path = os.path.join(video_history_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest_path

def cleanup(history_dir="history"):
    # Get video file name
    video_file = find_video_files()
    video_name = os.path.splitext(os.path.basename(video_file))[0]
    video_name = sanitize_filename(video_name)
    
    # Create required folders
    os.makedirs(history_dir, exist_ok=True)
    video_history_dir = os.path.join(history_dir, video_name)
    log_dir = os.path.join(video_history_dir, "log")
    gpt_log_dir = os.path.join(video_history_dir, "gpt_log")
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(gpt_log_dir, exist_ok=True)

    # Move non-log files
    for file in glob.glob("output/*"):
        if not file.endswith(('log', 'gpt_log')):
            move_file(file, video_history_dir)

    # Move log files
    for file in glob.glob("output/log/*"):
        move_file(file, log_dir)

    # Move gpt_log files
    for file in glob.glob("output/gpt_log/*"):
        move_file(file, gpt_log_dir)

    _write_manifest(video_history_dir, os.path.basename(video_file))

    # Remove task status files that are only used by the GUI progress display.
    # They are hidden files, so glob("output/*") does not catch them.
    for file in glob.glob("output/.videolingo_task*"):
        try:
            os.remove(file)
            print(f"✅ Removed task status file: {file}")
        except OSError as e:
            print(f"⚠️ Could not remove task status file {file}: {e}")

    # Delete empty output directories
    try:
        os.rmdir("output/log")
        os.rmdir("output/gpt_log")
        os.rmdir("output")
    except OSError:
        pass  # Ignore errors when deleting directories

    return os.path.abspath(video_history_dir)

def move_file(src, dst):
    try:
        # Get the source file name
        src_filename = os.path.basename(src)
        # Use os.path.join to ensure correct path and include file name
        dst = os.path.join(dst, sanitize_filename(src_filename))
        
        if os.path.exists(dst):
            if os.path.isdir(dst):
                # If destination is a folder, try to delete its contents
                shutil.rmtree(dst, ignore_errors=True)
            else:
                # If destination is a file, try to delete it
                os.remove(dst)
        
        shutil.move(src, dst, copy_function=shutil.copy2)
        print(f"✅ Moved: {src} -> {dst}")
    except PermissionError:
        print(f"⚠️ Permission error: Cannot delete {dst}, attempting to overwrite")
        try:
            shutil.copy2(src, dst)
            os.remove(src)
            print(f"✅ Copied and deleted source file: {src} -> {dst}")
        except Exception as e:
            print(f"❌ Move failed: {src} -> {dst}")
            print(f"Error message: {str(e)}")
    except Exception as e:
        print(f"❌ Move failed: {src} -> {dst}")
        print(f"Error message: {str(e)}")

def sanitize_filename(filename):
    # Remove or replace disallowed characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename

if __name__ == "__main__":
    cleanup()
