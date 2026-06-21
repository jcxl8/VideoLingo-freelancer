import json
import stat
import tempfile
import threading
import unittest
from pathlib import Path


class AtomicFilesTest(unittest.TestCase):
    def test_atomic_json_round_trip_and_permissions(self):
        from core.utils.atomic_files import atomic_write_json

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            atomic_write_json(path, {"status": "running"}, mode=0o600)

            data = json.loads(path.read_text(encoding="utf-8"))
            mode = stat.S_IMODE(path.stat().st_mode)

        self.assertEqual(data, {"status": "running"})
        self.assertEqual(mode, 0o600)

    def test_concurrent_readers_only_see_complete_json(self):
        from core.utils.atomic_files import atomic_write_json

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            atomic_write_json(path, {"version": 0, "payload": "x" * 1000})
            errors = []

            def writer():
                for version in range(1, 80):
                    atomic_write_json(
                        path, {"version": version, "payload": "x" * 1000}
                    )

            thread = threading.Thread(target=writer)
            thread.start()
            while thread.is_alive():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if len(data.get("payload", "")) != 1000:
                        errors.append("partial payload")
                except Exception as exc:
                    errors.append(type(exc).__name__)
            thread.join()

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
