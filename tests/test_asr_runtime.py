import unittest

from core import _2_asr


class ASRRuntimeTests(unittest.TestCase):
    def test_unknown_runtime_falls_back_to_mlx(self):
        self.assertEqual(_2_asr.resolve_asr_runtime("removed-runtime"), "mlx")

    def test_supported_runtimes_are_preserved(self):
        self.assertEqual(_2_asr.resolve_asr_runtime("local"), "local")
        self.assertEqual(_2_asr.resolve_asr_runtime("mlx"), "mlx")


if __name__ == "__main__":
    unittest.main()
