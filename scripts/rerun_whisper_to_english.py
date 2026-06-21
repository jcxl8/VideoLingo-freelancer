import argparse
import json
import os
import time

import pandas as pd
from rich import print as rprint

from core.asr_backend.audio_preprocess import (
    FILLER_WORDS,
    REPEATABLE_FILLER_CONNECTORS,
    _clean_word_token,
    _is_filler_word,
    _near_duplicate_content_mask,
    _near_duplicate_subtoken_mask,
    _normalize_english_pronoun_i,
    process_transcription,
    split_audio,
)
from core.asr_backend.whisperX_local import transcribe_audio_segments
from core.utils.models import _RAW_AUDIO_FILE, _VOCAL_AUDIO_FILE


def clean_transcription_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["text"] = df["text"].apply(_normalize_english_pronoun_i)
    df = df[df["text"].astype(str).str.len() > 0].copy()
    df = df[df["text"].astype(str).str.len() <= 30].copy()
    df = df[~df["text"].apply(_is_filler_word)].copy()

    duplicate_mask = []
    previous_word = ""
    for word in df["text"]:
        current_word = _clean_word_token(word)
        duplicate_mask.append(
            bool(current_word)
            and current_word == previous_word
            and current_word in REPEATABLE_FILLER_CONNECTORS
        )
        previous_word = current_word
    duplicate_mask = pd.Series(duplicate_mask, index=df.index, dtype=bool)
    df = df[~duplicate_mask].copy()

    near_duplicate_mask = _near_duplicate_content_mask(df)
    df = df[~near_duplicate_mask].copy()

    subtoken_duplicate_mask = _near_duplicate_subtoken_mask(df)
    return df[~subtoken_duplicate_mask].copy()


def collect_gaps(df: pd.DataFrame, threshold: float):
    gaps = []
    previous = None
    for _, row in df.iterrows():
        if previous is not None:
            gap = float(row.start) - float(previous.end)
            if gap >= threshold:
                gaps.append(
                    {
                        "gap": round(gap, 3),
                        "start": round(float(previous.end), 3),
                        "end": round(float(row.start), 3),
                        "previous_word": str(previous.text),
                        "next_word": str(row.text),
                    }
                )
        previous = row
    return gaps


def main():
    parser = argparse.ArgumentParser(description="Rerun local Whisper English transcription without touching active outputs.")
    parser.add_argument("--raw-audio", default=_RAW_AUDIO_FILE)
    parser.add_argument("--vocal-audio", default=_VOCAL_AUDIO_FILE)
    parser.add_argument("--target-len", type=float, default=30)
    parser.add_argument("--window", type=float, default=10)
    parser.add_argument("--gap-threshold", type=float, default=2.5)
    parser.add_argument("--xlsx", default="output/log/cleaned_chunks_whisper_rerun.xlsx")
    parser.add_argument("--txt", default="output/log/whisper_rerun_text.txt")
    parser.add_argument("--gaps-json", default="output/log/whisper_rerun_gaps.json")
    args = parser.parse_args()

    started = time.time()
    os.makedirs(os.path.dirname(args.xlsx), exist_ok=True)

    rprint(f"[cyan]🎙️ Rerun Whisper English transcription[/cyan]")
    rprint(f"[cyan]Raw audio:[/cyan] {args.raw_audio}")
    rprint(f"[cyan]Vocal audio:[/cyan] {args.vocal_audio}")
    segments = split_audio(args.raw_audio, target_len=args.target_len, win=args.window)
    rprint(f"[cyan]Segments:[/cyan] {len(segments)}")

    result = transcribe_audio_segments(args.raw_audio, args.vocal_audio, segments)
    df = process_transcription(result)
    df = clean_transcription_df(df)
    df = df.sort_values(["start", "end"], kind="stable").reset_index(drop=True)

    export_df = df.copy()
    export_df["text"] = export_df["text"].apply(lambda value: f'"{value}"')
    export_df.to_excel(args.xlsx, index=False)

    text = " ".join(str(value).strip() for value in df["text"].tolist())
    with open(args.txt, "w", encoding="utf-8") as file:
        file.write(text.strip() + "\n")

    gaps = collect_gaps(df, args.gap_threshold)
    with open(args.gaps_json, "w", encoding="utf-8") as file:
        json.dump(gaps, file, ensure_ascii=False, indent=2)

    rprint(f"[green]✅ Saved:[/green] {args.xlsx}")
    rprint(f"[green]✅ Saved:[/green] {args.txt}")
    rprint(f"[green]✅ Saved:[/green] {args.gaps_json}")
    rprint(f"[cyan]Rows:[/cyan] {len(df)}")
    rprint(f"[cyan]Gaps >= {args.gap_threshold}s:[/cyan] {len(gaps)}")
    rprint(f"[cyan]Elapsed:[/cyan] {time.time() - started:.1f}s")


if __name__ == "__main__":
    main()
