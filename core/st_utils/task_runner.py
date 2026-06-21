from __future__ import annotations

import json
import os
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterable

from core.st_utils import task_state
from core.utils.atomic_files import atomic_write_json


PROCESS_CONTROL = "output/.videolingo_task_control.json"


class StopTask(Exception):
    """Raised when the current task is stopped at a step boundary."""


def _now():
    return time.time()


def _read_control():
    if not os.path.exists(PROCESS_CONTROL):
        return {}
    try:
        with open(PROCESS_CONTROL, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_control(action, task_name=None):
    atomic_write_json(
        PROCESS_CONTROL,
        {
            "action": action,
            "task": task_name,
            "updated_at": _now(),
        },
    )


def _clear_control():
    if os.path.exists(PROCESS_CONTROL):
        try:
            os.remove(PROCESS_CONTROL)
        except OSError:
            pass


@dataclass
class TaskRunner:
    """Persistent task runner for Streamlit workflows.

    The upstream runner keeps state in Streamlit session memory. This local
    variant keeps the lock/status/control files in output/ so refreshes and
    failures can be recovered from the GUI.
    """

    total_steps: int = 0
    default_error_message: str = "No detailed error was recorded for this older failure."

    @staticmethod
    def get(session_state=None, key="_task_runner", **kwargs):
        if session_state is None:
            return TaskRunner(**kwargs)
        if key not in session_state:
            session_state[key] = TaskRunner(**kwargs)
        return session_state[key]

    @property
    def status(self):
        return task_state.read_task_status()

    @property
    def state(self):
        return self.status.get("status", "idle")

    @property
    def is_active(self):
        return self.is_running()

    @property
    def is_done(self):
        return self.state in ("completed", "stopped", "failed", "error")

    @property
    def progress(self):
        status = self.status
        total_steps = int(status.get("total_steps") or self.total_steps or 0)
        current_step = int(status.get("step_index") or 0)
        if total_steps <= 0:
            return 0.0
        return min(max(current_step, 0), total_steps) / total_steps

    def read_status(self):
        return task_state.read_task_status()

    def write_status(
        self,
        task_name,
        status="running",
        step_index=None,
        step_label=None,
        step_times=None,
        error_message=None,
        error_traceback=None,
        total_steps=None,
    ):
        task_state.write_task_status(
            task_name,
            status=status,
            step_index=step_index,
            step_label=step_label,
            step_times=step_times,
            error_message=error_message,
            error_traceback=error_traceback,
            default_error_message=self.default_error_message,
            total_steps=total_steps if total_steps is not None else self.total_steps,
        )

    def clear_status(self):
        task_state.clear_task_status()

    def is_running(self):
        return task_state.is_task_running()

    def request_pause(self, task_name=None):
        _write_control("pause", task_name)

    def resume(self, task_name=None):
        _write_control("resume", task_name)

    def stop(self, task_name=None, message=None):
        _write_control("stop", task_name)
        status = self.read_status()
        if status.get("status") in ("running", "paused"):
            self.write_status(
                status.get("task") or task_name or "task",
                status="stopping",
                step_index=status.get("step_index"),
                step_label=status.get("step_label"),
                step_times=status.get("step_times", {}),
                error_message=message or "Stop requested. The task will stop at the next safe step boundary.",
                total_steps=status.get("total_steps") or self.total_steps,
            )

    def reset(self):
        if not self.is_running():
            self.clear_status()
            _clear_control()

    def sync_status(self, stopped_message, refresh_message):
        status = self.read_status()
        if status.get("status") == "failed" and task_state.is_streamlit_control_traceback(status):
            task_state.remove_process_lock()
            self.write_status(
                status.get("task") or "task",
                status="stopped",
                step_index=status.get("step_index"),
                step_label=status.get("step_label"),
                step_times=status.get("step_times", {}),
                error_message=refresh_message,
                total_steps=status.get("total_steps") or self.total_steps,
            )
            return self.read_status()

        if status.get("status") not in ("running", "paused", "stopping"):
            return status

        if self.is_running():
            return status

        task_state.remove_process_lock()
        self.write_status(
            status.get("task") or "task",
            status="stopped",
            step_index=status.get("step_index"),
            step_label=status.get("step_label"),
            step_times=status.get("step_times", {}),
            error_message=stopped_message,
            total_steps=status.get("total_steps") or self.total_steps,
        )
        return self.read_status()

    @contextmanager
    def guard(
        self,
        task_name,
        reset_status=True,
        before_reset=None,
        complete_status="completed",
        clear_status_on_success=False,
        streamlit_interrupted_message="The task was interrupted by a page refresh or Streamlit rerun.",
    ):
        if self.is_running():
            raise RuntimeError("A task is already running. Please wait until it finishes.")

        task_state.write_process_lock(task_name)
        heartbeat = task_state.start_process_heartbeat()
        if reset_status:
            if before_reset:
                before_reset()
            self.clear_status()
            _clear_control()
            self.write_status(task_name, status="running", total_steps=self.total_steps)

        try:
            yield self
        except StopTask:
            task_state.remove_process_lock()
            return
        except Exception as exc:
            status = self.read_status()
            if task_state.is_streamlit_control_exception(type(exc)):
                self.write_status(
                    task_name,
                    status="stopped",
                    step_index=status.get("step_index"),
                    step_label=status.get("step_label"),
                    step_times=status.get("step_times", {}),
                    error_message=streamlit_interrupted_message,
                    total_steps=status.get("total_steps") or self.total_steps,
                )
                task_state.remove_process_lock()
                raise
            self.write_status(
                task_name,
                status="failed",
                step_index=status.get("step_index"),
                step_label=status.get("step_label"),
                step_times=status.get("step_times", {}),
                error_message=exc,
                error_traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                total_steps=status.get("total_steps") or self.total_steps,
            )
            task_state.remove_process_lock()
            raise
        else:
            status = self.read_status()
            if clear_status_on_success:
                self.clear_status()
            elif status.get("status") not in ("awaiting_review", "stopped", "failed"):
                self.write_status(
                    task_name,
                    status=complete_status,
                    step_index=status.get("step_index"),
                    step_label=status.get("step_label"),
                    step_times=status.get("step_times", {}),
                    total_steps=status.get("total_steps") or self.total_steps,
                )
        finally:
            heartbeat.set()
            task_state.remove_process_lock()

    def _wait_if_paused_or_stopped(self, task_name):
        while True:
            control = _read_control()
            action = control.get("action")
            control_task = control.get("task")
            if control_task and control_task != task_name:
                return
            status = self.read_status()
            if action == "stop":
                self.write_status(
                    task_name,
                    status="stopped",
                    step_index=status.get("step_index"),
                    step_label=status.get("step_label"),
                    step_times=status.get("step_times", {}),
                    error_message="Task stopped by user.",
                    total_steps=status.get("total_steps") or self.total_steps,
                )
                task_state.remove_process_lock()
                raise StopTask("Task stopped by user.")
            if action != "pause":
                if action == "resume":
                    _clear_control()
                    if status.get("status") == "paused":
                        self.write_status(
                            task_name,
                            status="running",
                            step_index=status.get("step_index"),
                            step_label=status.get("step_label"),
                            step_times=status.get("step_times", {}),
                            total_steps=status.get("total_steps") or self.total_steps,
                        )
                return
            if status.get("status") != "paused":
                self.write_status(
                    task_name,
                    status="paused",
                    step_index=status.get("step_index"),
                    step_label=status.get("step_label"),
                    step_times=status.get("step_times", {}),
                    total_steps=status.get("total_steps") or self.total_steps,
                )
            task_state.touch_process_lock()
            time.sleep(1)

    def run_step(self, task_name, step_index, step_label, callback, on_progress=None):
        self._wait_if_paused_or_stopped(task_name)
        status = self.read_status()
        step_times = status.get("step_times", {})
        step_times[str(step_index)] = {"start": _now()}
        self.write_status(
            task_name,
            status="running",
            step_index=step_index,
            step_label=step_label,
            step_times=step_times,
            total_steps=status.get("total_steps") or self.total_steps,
        )
        if on_progress:
            on_progress(step_index)
        try:
            result = callback()
        except Exception as exc:
            self.write_status(
                task_name,
                status="failed",
                step_index=step_index,
                step_label=step_label,
                step_times=step_times,
                error_message=exc,
                error_traceback=traceback.format_exc(),
                total_steps=status.get("total_steps") or self.total_steps,
            )
            task_state.remove_process_lock()
            raise

        status = self.read_status()
        step_times = status.get("step_times", step_times)
        timing = step_times.get(str(step_index), {})
        end_time = _now()
        timing["end"] = end_time
        timing["elapsed"] = end_time - timing.get("start", end_time)
        step_times[str(step_index)] = timing
        self.write_status(
            task_name,
            status="running",
            step_index=step_index,
            step_label=step_label,
            step_times=step_times,
            total_steps=status.get("total_steps") or self.total_steps,
        )
        if on_progress:
            on_progress(step_index)
        self._wait_if_paused_or_stopped(task_name)
        return result

    def run_steps(self, task_name, steps: Iterable[tuple[int, str, Callable]], start_step=1, on_progress=None):
        results = {}
        for step_index, step_label, callback in steps:
            if step_index >= start_step:
                results[step_index] = self.run_step(
                    task_name,
                    step_index,
                    step_label,
                    callback,
                    on_progress=on_progress,
                )
        return results

    @staticmethod
    def total_elapsed_time(status):
        step_times = status.get("step_times", {})
        elapsed_values = [
            float(timing.get("elapsed"))
            for timing in step_times.values()
            if isinstance(timing, dict) and timing.get("elapsed") is not None
        ]
        if elapsed_values:
            return sum(elapsed_values)
        started_at = status.get("started_at")
        updated_at = status.get("updated_at")
        if started_at and updated_at:
            return max(0, float(updated_at) - float(started_at))
        return None

    @staticmethod
    def estimate_remaining_time(status, current_step, total_steps):
        if not current_step or status.get("status") != "running":
            return None

        step_times = status.get("step_times", {})
        completed = [
            timing.get("elapsed")
            for timing in step_times.values()
            if isinstance(timing, dict) and timing.get("elapsed") is not None
        ]
        completed = [float(item) for item in completed if float(item) >= 0]

        now = _now()
        current_timing = step_times.get(str(current_step), {})
        current_elapsed = 0
        if current_timing.get("start"):
            current_elapsed = max(0, now - float(current_timing.get("start")))

        if completed:
            average_step_time = sum(completed) / len(completed)
        elif current_elapsed:
            average_step_time = current_elapsed
        else:
            return None

        current_remaining = max(average_step_time - current_elapsed, 0)
        future_steps = max(total_steps - current_step, 0)
        return current_remaining + future_steps * average_step_time
