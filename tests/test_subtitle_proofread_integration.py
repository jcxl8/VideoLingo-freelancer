import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SubtitleProofreadIntegrationTest(unittest.TestCase):
    def test_enabled_by_default_and_runs_after_final_srt_generation(self):
        config = (ROOT / "config.yaml").read_text(encoding="utf-8")
        source = (ROOT / "core/_6_gen_sub.py").read_text(encoding="utf-8")

        self.assertIn("enable_subtitle_proofread: true", config)
        function = source[source.index("def align_timestamp_main"):]
        proofread_position = function.index("proofread_subtitle_set(")
        self.assertIn("subtitle_paths", function[proofread_position:proofread_position + 120])
        self.assertIn("auto_fix=True", function[proofread_position:proofread_position + 220])
        ambiguity_position = function.index("write_ambiguity_report(df_trans_time)")
        audio_position = function.index("# for audio")
        self.assertLess(proofread_position, ambiguity_position)
        self.assertLess(proofread_position, audio_position)

    def test_gui_renders_report_before_merge_and_with_outputs(self):
        source = (ROOT / "st.py").read_text(encoding="utf-8")

        self.assertIn("def _render_subtitle_proofread_report():", source)
        outputs = source[source.index("def _render_subtitle_outputs_without_video"):source.index("def _render_merged_video_preview")]
        self.assertIn("_render_subtitle_proofread_report()", outputs)
        review = source[source.index("if _subtitle_review_pending():"):source.index("if not sub_video:")]
        self.assertIn("_render_subtitle_proofread_report()", review)

    def test_retranslation_clears_stale_reports(self):
        source = (ROOT / "core/st_utils/retranslation.py").read_text(encoding="utf-8")
        self.assertIn("output/log/subtitle_proofread_report.json", source)
        self.assertIn("output/subtitle_proofread_report.md", source)


if __name__ == "__main__":
    unittest.main()
