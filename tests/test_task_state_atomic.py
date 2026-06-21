import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.st_utils import task_runner, task_state


class TaskStateAtomicTest(unittest.TestCase):
    def test_status_lock_and_control_files_are_complete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lock_path = root / "task.lock"
            status_path = root / "status.json"
            control_path = root / "control.json"
            with patch.object(task_state, "PROCESS_LOCK", str(lock_path)), patch.object(
                task_state, "PROCESS_STATUS", str(status_path)
            ), patch.object(task_runner, "PROCESS_CONTROL", str(control_path)):
                task_id = task_state.write_process_lock("subtitle")
                task_state.touch_process_lock()
                task_state.write_task_status(
                    "subtitle", status="running", step_index=2, task_id=task_id
                )
                task_runner._write_control("pause", "subtitle")

                lock = task_state.read_process_lock()
                status = json.loads(status_path.read_text(encoding="utf-8"))
                control = json.loads(control_path.read_text(encoding="utf-8"))

        self.assertEqual(lock["task"], "subtitle")
        self.assertEqual(lock["task_id"], task_id)
        self.assertEqual(status["status"], "running")
        self.assertEqual(control["action"], "pause")

    def test_corrupt_status_is_preserved_and_reported_as_stopped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            status_path = Path(tmpdir) / "status.json"
            status_path.write_text('{"status":', encoding="utf-8")
            with patch.object(task_state, "PROCESS_STATUS", str(status_path)):
                result = task_state.read_task_status()
                preserved = list(status_path.parent.glob("status.json.corrupt-*"))

        self.assertEqual(result["status"], "stopped")
        self.assertIn("invalid JSON", result["error_message"])
        self.assertEqual(len(preserved), 1)


if __name__ == "__main__":
    unittest.main()
