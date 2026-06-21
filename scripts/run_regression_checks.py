#!/usr/bin/env python3
"""Regression checks for local subtitle quality rules."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core._6_gen_sub import get_sentence_timestamps  # noqa: E402
from core.spacy_utils.merge_short_segments import merge_lines  # noqa: E402
from core.utils.text_normalize import normalize_cjk_latin_spacing  # noqa: E402


def check_short_segment_merge():
    merged = merge_lines([
        "I want",
        "to start now.",
        "This is already a complete sentence.",
    ])
    assert merged[0] == "I want to start now.", merged
    assert merged[1] == "This is already a complete sentence.", merged


def check_cjk_latin_spacing():
    text = normalize_cjk_latin_spacing("工作流模型API密钥有效，iPhone手机支持AI功能")
    assert text == "工作流模型 API 密钥有效，iPhone 手机支持 AI 功能", text


def check_leading_ack_timestamp_trim():
    df_words = pd.DataFrame([
        {"text": "Thank", "start": 0.0, "end": 8.0},
        {"text": "you", "start": 8.1, "end": 9.0},
        {"text": "Blazing", "start": 33.871, "end": 34.2},
        {"text": "saddles", "start": 34.21, "end": 34.7},
        {"text": "and", "start": 34.71, "end": 34.9},
        {"text": "all", "start": 34.91, "end": 35.1},
        {"text": "in", "start": 35.11, "end": 35.2},
        {"text": "the", "start": 35.21, "end": 35.3},
        {"text": "family", "start": 35.31, "end": 35.8},
    ])
    df_sentences = pd.DataFrame([
        {"Source": "Thank you. Blazing saddles and all in the family", "Translation": "谢谢。《闪亮的马鞍》和《一家子》"},
    ])
    timestamps = get_sentence_timestamps(df_words, df_sentences)
    assert timestamps[0]["speech_start"] == 33.871, timestamps
    assert df_sentences.loc[0, "Source"] == "Blazing saddles and all in the family"


def main():
    check_short_segment_merge()
    check_cjk_latin_spacing()
    check_leading_ack_timestamp_trim()
    print("Regression checks OK")


if __name__ == "__main__":
    main()
