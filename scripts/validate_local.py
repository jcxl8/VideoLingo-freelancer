#!/usr/bin/env python3
"""Lightweight local validation for the customized VideoLingo build."""

from __future__ import annotations

import json
import py_compile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PYTHON_FILES = [
    "st.py",
    "core/_1_ytdlp.py",
    "core/_3_1_split_nlp.py",
    "core/_3_2_split_meaning.py",
    "core/_4_1_summarize.py",
    "core/_4_2_translate.py",
    "core/_6_gen_sub.py",
    "core/_7_sub_into_vid.py",
    "core/asr_backend/audio_preprocess.py",
    "core/st_utils/download_video_section.py",
    "core/st_utils/sidebar_setting.py",
    "core/st_utils/task_state.py",
    "core/st_utils/upload_copy.py",
    "core/translate_lines.py",
    "core/utils/ask_gpt.py",
    "core/utils/config_utils.py",
    "core/utils/model_router.py",
    "core/utils/onekeycleanup.py",
    "core/utils/text_normalize.py",
]

JSON_FILES = [
    "translations/en.json",
    "translations/zh-CN.json",
]


def compile_python() -> list[str]:
    errors: list[str] = []
    for rel_path in PYTHON_FILES:
        path = ROOT / rel_path
        if not path.exists():
            errors.append(f"missing python file: {rel_path}")
            continue
        try:
            py_compile.compile(str(path), doraise=True)
        except Exception as exc:  # pragma: no cover - command-line diagnostic
            errors.append(f"{rel_path}: {exc}")
    return errors


def validate_json() -> list[str]:
    errors: list[str] = []
    for rel_path in JSON_FILES:
        path = ROOT / rel_path
        if not path.exists():
            errors.append(f"missing json file: {rel_path}")
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{rel_path}: {exc}")
    return errors


def main() -> int:
    errors = compile_python() + validate_json()
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Validation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
