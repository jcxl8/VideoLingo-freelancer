import os
import tempfile
import unittest

from core.st_utils.retranslation import clean_retranslation_outputs


class RetranslationCleanupTest(unittest.TestCase):
    def test_clean_retranslation_outputs_removes_only_translation_downstream_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            keep_files = [
                "output/log/cleaned_chunks.xlsx",
                "output/log/split_by_nlp.txt",
                "output/log/split_by_meaning.txt",
            ]
            remove_files = [
                "output/log/translation_results.xlsx",
                "output/log/.translation_model_cache",
                "output/log/translation_results_for_subtitles.xlsx",
                "output/log/translation_results_remerged.xlsx",
                "output/log/ambiguity_report.json",
                "output/ambiguity_report.md",
                "output/audio/trans_subs_for_audio.srt",
            ]
            for rel_path in keep_files + remove_files:
                path = os.path.join(tmp, rel_path)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write("x")

            removed = clean_retranslation_outputs(tmp)

            for rel_path in keep_files:
                self.assertTrue(os.path.exists(os.path.join(tmp, rel_path)), rel_path)
            for rel_path in remove_files:
                self.assertFalse(os.path.exists(os.path.join(tmp, rel_path)), rel_path)
            self.assertEqual(set(remove_files), set(removed))


if __name__ == "__main__":
    unittest.main()
