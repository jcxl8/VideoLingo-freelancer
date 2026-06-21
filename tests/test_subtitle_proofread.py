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


if __name__ == "__main__":
    unittest.main()
