import subprocess
import sys
import textwrap
import unittest


class LightweightAsrImportsTest(unittest.TestCase):
    def test_asr_helpers_import_without_ml_runtime_dependencies(self):
        script = textwrap.dedent(
            """
            import importlib.abc
            import sys

            class BlockHeavyImports(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.split('.', 1)[0] in {'torch', 'whisperx', 'faster_whisper'}:
                        raise ModuleNotFoundError(fullname)
                    return None

            sys.meta_path.insert(0, BlockHeavyImports())
            from core import _2_asr
            from core.asr_backend import whisperX_local
            assert _2_asr.resolve_asr_runtime('local') == 'local'
            assert whisperX_local._WHISPERX_SR == 16000
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
