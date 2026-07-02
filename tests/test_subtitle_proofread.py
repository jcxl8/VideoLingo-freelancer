import json
import tempfile
import unittest
from pathlib import Path

from core.subtitle_proofread import proofread_subtitle_set


def _write_srt(path, entries):
    blocks = []
    for index, start, end, lines in entries:
        text = "\n".join(lines if isinstance(lines, list) else [lines])
        blocks.append(f"{index}\n{start} --> {end}\n{text}")
    Path(path).write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


class SubtitleProofreadTest(unittest.TestCase):
    def test_reports_structural_fragment_and_bilingual_issues(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {key: root / f"{key}.srt" for key in ("src", "trans", "src_trans", "trans_src")}
            src_entries = [
                (1, "00:00:00,000", "00:00:01,000", "Twitter is a war"),
                (2, "00:00:00,900", "00:00:01,100", "zone."),
            ]
            trans_entries = [
                (1, "00:00:00,000", "00:00:01,000", "推特就是个战场"),
                (2, "00:00:01,000", "00:00:01,100", "这个战区内容非常长而且阅读时间明显不足"),
            ]
            _write_srt(paths["src"], src_entries)
            _write_srt(paths["trans"], trans_entries)
            _write_srt(paths["src_trans"], [
                (1, "00:00:00,000", "00:00:01,000", ["Twitter is a war", "推特就是个战场"]),
            ])
            _write_srt(paths["trans_src"], [
                (1, "00:00:00,000", "00:00:01,000", ["错误译文", "Twitter is a war"]),
                (2, "00:00:01,000", "00:00:01,100", ["这个战区内容非常长而且阅读时间明显不足", "zone."]),
            ])

            report = proofread_subtitle_set(
                paths,
                report_json=root / "report.json",
                report_md=root / "report.md",
            )

            issue_types = {item["type"] for item in report["issues"]}
            self.assertIn("entry_count_mismatch", issue_types)
            self.assertIn("timestamp_overlap", issue_types)
            self.assertIn("source_fragment", issue_types)
            self.assertIn("translation_cps", issue_types)
            self.assertIn("bilingual_text_mismatch", issue_types)
            self.assertEqual(json.loads((root / "report.json").read_text())["status"], "issues_found")
            self.assertIn("Subtitle Proofread Report", (root / "report.md").read_text())

    def test_clean_aligned_set_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {key: root / f"{key}.srt" for key in ("src", "trans", "src_trans", "trans_src")}
            source = "Twitter is a war zone."
            translation = "推特就是个战场"
            timestamp = (1, "00:00:00,000", "00:00:02,000")
            _write_srt(paths["src"], [(*timestamp, source)])
            _write_srt(paths["trans"], [(*timestamp, translation)])
            _write_srt(paths["src_trans"], [(*timestamp, [source, translation])])
            _write_srt(paths["trans_src"], [(*timestamp, [translation, source])])

            report = proofread_subtitle_set(paths)

            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["issues"], [])
            self.assertEqual(report["summary"]["entry_count"], 1)

    def test_reports_semantic_translation_alignment_issues(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {key: root / f"{key}.srt" for key in ("src", "trans", "src_trans", "trans_src")}
            entries = [
                (
                    1,
                    "00:00:00,000",
                    "00:00:01,000",
                    "You know?",
                    "第一次录《60 分钟》时",
                ),
                (
                    2,
                    "00:00:01,000",
                    "00:00:03,000",
                    "I'm Bob Simon. It didn't go perfectly though.",
                    "不过录得不太顺利",
                ),
                (
                    3,
                    "00:00:03,000",
                    "00:00:04,000",
                    "I'm Anderson Cooper.",
                    "都得录上十次左右 我是安德森·库珀",
                ),
            ]
            _write_srt(paths["src"], [(idx, start, end, source) for idx, start, end, source, _ in entries])
            _write_srt(paths["trans"], [(idx, start, end, translation) for idx, start, end, _, translation in entries])
            _write_srt(paths["src_trans"], [
                (idx, start, end, [source, translation])
                for idx, start, end, source, translation in entries
            ])
            _write_srt(paths["trans_src"], [
                (idx, start, end, [translation, source])
                for idx, start, end, source, translation in entries
            ])

            report = proofread_subtitle_set(paths)

            issue_types = {item["type"] for item in report["issues"]}
            self.assertIn("semantic_alignment_suspicion", issue_types)
            self.assertIn("question_translation_mismatch", issue_types)
            self.assertIn("translation_omission", issue_types)

    def test_auto_fixes_deterministic_shifted_translation_tails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {key: root / f"{key}.srt" for key in ("src", "trans", "src_trans", "trans_src")}
            entries = [
                (
                    1,
                    "00:00:00,000",
                    "00:00:03,000",
                    "like ten I'ms for each one that actually gets on the air.",
                    "每条真正播出的 I'm 介绍",
                ),
                (
                    2,
                    "00:00:03,000",
                    "00:00:04,000",
                    "I'm Anderson Cooper.",
                    "都得录上十次左右 我是安德森·库珀",
                ),
                (
                    3,
                    "00:00:04,000",
                    "00:00:05,000",
                    "You know?",
                    "第一次为《60 分钟》录音",
                ),
                (
                    4,
                    "00:00:05,000",
                    "00:00:08,000",
                    "It is a little the first time you do it for 60 minutes.",
                    "感觉就是 天啊",
                ),
            ]
            _write_srt(paths["src"], [(idx, start, end, source) for idx, start, end, source, _ in entries])
            _write_srt(paths["trans"], [(idx, start, end, translation) for idx, start, end, _, translation in entries])
            _write_srt(paths["src_trans"], [
                (idx, start, end, [source, translation])
                for idx, start, end, source, translation in entries
            ])
            _write_srt(paths["trans_src"], [
                (idx, start, end, [translation, source])
                for idx, start, end, source, translation in entries
            ])

            report = proofread_subtitle_set(paths, auto_fix=True)

            self.assertEqual(report["summary"]["fix_count"], 2)
            trans_text = paths["trans"].read_text(encoding="utf-8")
            self.assertIn("每条真正播出的 I'm 介绍 都得录上十次左右", trans_text)
            self.assertIn("我是安德森·库珀", trans_text)
            self.assertIn("你懂吧？", trans_text)
            self.assertIn("第一次为《60 分钟》录音 感觉就是 天啊", trans_text)
            self.assertIn("You know?\n你懂吧？", paths["src_trans"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
