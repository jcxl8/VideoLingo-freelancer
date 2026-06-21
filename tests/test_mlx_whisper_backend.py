import unittest
from unittest.mock import patch

from core.asr_backend import mlx_whisper_local


class MlxWhisperBackendTest(unittest.TestCase):
    def test_normalises_mlx_word_timestamps_to_videolingo_segments(self):
        result = {
            "language": "en",
            "segments": [
                {
                    "text": "Hello world.",
                    "start": 1.0,
                    "end": 2.0,
                    "words": [
                        {"word": " Hello", "start": 1.0, "end": 1.4},
                        {"word": " world.", "start": 1.45, "end": 2.0},
                    ],
                }
            ],
        }

        normalised = mlx_whisper_local._normalise_mlx_result(result)

        self.assertEqual(normalised["language"], "en")
        self.assertEqual(len(normalised["segments"]), 1)
        self.assertEqual(normalised["segments"][0]["text"], "Hello world.")
        self.assertEqual(
            normalised["segments"][0]["words"],
            [
                {"word": "Hello", "start": 1.0, "end": 1.4},
                {"word": "world.", "start": 1.45, "end": 2.0},
            ],
        )

    def test_preserves_decoder_quality_metadata(self):
        result = {
            "language": "en",
            "segments": [
                {
                    "text": "Hello.",
                    "start": 1.0,
                    "end": 1.5,
                    "avg_logprob": -0.25,
                    "no_speech_prob": 0.04,
                    "compression_ratio": 0.8,
                    "words": [
                        {
                            "word": " Hello.",
                            "start": 1.0,
                            "end": 1.5,
                            "probability": 0.97,
                        }
                    ],
                }
            ],
        }

        segment = mlx_whisper_local._normalise_mlx_result(result)["segments"][0]

        self.assertEqual(segment["avg_logprob"], -0.25)
        self.assertEqual(segment["no_speech_prob"], 0.04)
        self.assertEqual(segment["compression_ratio"], 0.8)
        self.assertEqual(segment["words"][0]["probability"], 0.97)

    def test_rejects_reproduced_silent_tail_hallucination(self):
        result = {
            "language": "en",
            "segments": [
                {
                    "text": " Thank you.",
                    "start": 66.30,
                    "end": 66.42,
                    "avg_logprob": -0.8876,
                    "no_speech_prob": 0.9117,
                    "compression_ratio": 0.56,
                    "words": [
                        {
                            "word": " Thank",
                            "start": 66.30,
                            "end": 66.42,
                            "probability": 0.0964,
                        },
                        {
                            "word": " you.",
                            "start": 66.42,
                            "end": 66.42,
                            "probability": 0.9946,
                        },
                    ],
                }
            ],
        }

        normalised = mlx_whisper_local._normalise_mlx_result(result)

        self.assertEqual(normalised["segments"], [])

    def test_keeps_credible_short_thank_you(self):
        result = {
            "language": "en",
            "segments": [
                {
                    "text": " Thank you.",
                    "start": 10.0,
                    "end": 10.8,
                    "avg_logprob": -0.2,
                    "no_speech_prob": 0.03,
                    "compression_ratio": 0.56,
                    "words": [
                        {
                            "word": " Thank",
                            "start": 10.0,
                            "end": 10.35,
                            "probability": 0.98,
                        },
                        {
                            "word": " you.",
                            "start": 10.35,
                            "end": 10.8,
                            "probability": 0.99,
                        },
                    ],
                }
            ],
        }

        normalised = mlx_whisper_local._normalise_mlx_result(result)

        self.assertEqual([segment["text"] for segment in normalised["segments"]], ["Thank you."])

    def test_keeps_faint_real_speech_when_only_one_defect_signal_exists(self):
        result = {
            "language": "en",
            "segments": [
                {
                    "text": " Yes, I did.",
                    "start": 20.0,
                    "end": 20.8,
                    "avg_logprob": -0.7,
                    "no_speech_prob": 0.84,
                    "compression_ratio": 0.7,
                    "words": [
                        {
                            "word": " Yes,",
                            "start": 20.0,
                            "end": 20.2,
                            "probability": 0.18,
                        },
                        {
                            "word": " I",
                            "start": 20.2,
                            "end": 20.4,
                            "probability": 0.91,
                        },
                        {
                            "word": " did.",
                            "start": 20.4,
                            "end": 20.8,
                            "probability": 0.93,
                        },
                    ],
                }
            ],
        }

        normalised = mlx_whisper_local._normalise_mlx_result(result)

        self.assertEqual([segment["text"] for segment in normalised["segments"]], ["Yes, I did."])

    def test_resolves_builtin_model_names_to_mlx_repos(self):
        with patch.object(mlx_whisper_local, "snapshot_download", side_effect=lambda repo_id, **_: f"/cache/{repo_id}"):
            self.assertEqual(
                mlx_whisper_local.resolve_mlx_whisper_model("large-v3"),
                "/cache/mlx-community/whisper-large-v3-mlx",
            )
            self.assertEqual(
                mlx_whisper_local.resolve_mlx_whisper_model("large-v3-turbo"),
                "/cache/mlx-community/whisper-large-v3-turbo",
            )

    def test_mlx_model_download_uses_single_worker_without_progress_bars(self):
        with patch.object(mlx_whisper_local, "disable_progress_bars") as disable:
            with patch.object(mlx_whisper_local, "snapshot_download", return_value="/cache/model") as download:
                self.assertEqual(mlx_whisper_local.resolve_mlx_whisper_model("large-v3"), "/cache/model")

        disable.assert_called_once()
        download.assert_called_once_with(
            repo_id="mlx-community/whisper-large-v3-mlx",
            max_workers=1,
            tqdm_class=None,
            resume_download=True,
        )


if __name__ == "__main__":
    unittest.main()
