import json
import os
import threading
import time
import uuid

from core.utils.atomic_files import atomic_write_json, atomic_write_text


PROCESS_LOCK = "output/.videolingo_task.lock"
PROCESS_STATUS = "output/.videolingo_task_status.json"
HEARTBEAT_STALE_SECONDS = 180
LEGACY_LOCK_GRACE_SECONDS = 30 * 60


def remove_process_lock():
    if os.path.exists(PROCESS_LOCK):
        try:
            os.remove(PROCESS_LOCK)
        except OSError:
            pass


def pid_is_alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def read_process_lock():
    if not os.path.exists(PROCESS_LOCK):
        return {}
    try:
        with open(PROCESS_LOCK, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()]
    except Exception:
        return {}

    data = {"task": lines[0] if lines else ""}
    for line in lines[1:]:
        if "=" in line:
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
        elif "started_at" not in data:
            data["started_at"] = line
    return data


def current_lock_task_id():
    return read_process_lock().get("task_id")


def _lock_heartbeat_age(lock):
    heartbeat_at = lock.get("heartbeat_at")
    if heartbeat_at:
        try:
            return time.time() - float(heartbeat_at)
        except (TypeError, ValueError):
            return None
    return None


def read_task_status():
    if not os.path.exists(PROCESS_STATUS):
        return {}
    try:
        with open(PROCESS_STATUS, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        corrupt_path = f"{PROCESS_STATUS}.corrupt-{time.time_ns()}"
        try:
            os.replace(PROCESS_STATUS, corrupt_path)
        except OSError:
            corrupt_path = ""
        result = {
            "status": "stopped",
            "error_message": "The task status file contains invalid JSON and was preserved for diagnosis.",
        }
        if corrupt_path:
            result["corrupt_status_path"] = corrupt_path
        return result
    except OSError:
        return {}


def is_task_running():
    if not os.path.exists(PROCESS_LOCK):
        return False

    status = read_task_status()
    if status.get("status") in ("failed", "stopped", "completed"):
        remove_process_lock()
        return False

    lock = read_process_lock()
    status_task_id = status.get("task_id")
    lock_task_id = lock.get("task_id")
    if status_task_id and lock_task_id and status_task_id != lock_task_id:
        remove_process_lock()
        return False

    heartbeat_age = _lock_heartbeat_age(lock)
    if heartbeat_age is not None:
        if heartbeat_age <= HEARTBEAT_STALE_SECONDS:
            return True
        remove_process_lock()
        if status.get("status") == "running":
            write_task_status(
                status.get("task") or lock.get("task") or "task",
                status="stopped",
                step_index=status.get("step_index"),
                step_label=status.get("step_label"),
                step_times=status.get("step_times", {}),
                error_message="The task heartbeat stopped. The GUI has unlocked this task.",
            )
        return False

    pid = lock.get("pid")
    if pid and not pid_is_alive(pid):
        remove_process_lock()
        return False

    try:
        lock_age = time.time() - os.path.getmtime(PROCESS_LOCK)
    except OSError:
        return False

    # Older lock files only contain the Streamlit server PID. That PID can stay
    # alive after a task has crashed, so use a short grace period instead of
    # treating it as a reliable task liveness signal.
    if lock_age > LEGACY_LOCK_GRACE_SECONDS:
        remove_process_lock()
        if status.get("status") == "running":
            write_task_status(
                status.get("task") or lock.get("task") or "task",
                status="stopped",
                step_index=status.get("step_index"),
                step_label=status.get("step_label"),
                step_times=status.get("step_times", {}),
                error_message="The old task lock expired. The GUI has unlocked this task.",
            )
        return False
    return True


def write_process_lock(task_name, task_id=None):
    task_id = task_id or uuid.uuid4().hex
    now = time.time()
    atomic_write_text(
        PROCESS_LOCK,
        f"{task_name}\n"
        f"task_id={task_id}\n"
        f"pid={os.getpid()}\n"
        f"started_at={now}\n"
        f"heartbeat_at={now}\n",
    )
    return task_id


def touch_process_lock():
    lock = read_process_lock()
    if not lock:
        return
    task_name = lock.get("task") or "task"
    started_at = lock.get("started_at") or str(time.time())
    lines = [f"{task_name}\n"]
    if lock.get("task_id"):
        lines.append(f"task_id={lock.get('task_id')}\n")
    if lock.get("pid"):
        lines.append(f"pid={lock.get('pid')}\n")
    lines.append(f"started_at={started_at}\n")
    lines.append(f"heartbeat_at={time.time()}\n")
    atomic_write_text(PROCESS_LOCK, "".join(lines))


def start_process_heartbeat(interval=15):
    stop_event = threading.Event()

    def run():
        while not stop_event.wait(interval):
            touch_process_lock()

    thread = threading.Thread(target=run, name="videolingo-task-heartbeat", daemon=True)
    thread.start()
    return stop_event


def write_task_status(
    task_name,
    status="running",
    step_index=None,
    step_label=None,
    step_times=None,
    error_message=None,
    error_traceback=None,
    default_error_message="No detailed error was recorded for this older failure.",
    total_steps=None,
    task_id=None,
):
    os.makedirs(os.path.dirname(PROCESS_STATUS), exist_ok=True)
    previous = read_task_status()
    data = {
        "task": task_name,
        "status": status,
        "step_index": step_index,
        "step_label": step_label,
        "started_at": previous.get("started_at", time.time()),
        "updated_at": time.time(),
        "step_times": step_times if step_times is not None else previous.get("step_times", {}),
    }
    resolved_task_id = task_id or previous.get("task_id") or current_lock_task_id()
    if resolved_task_id:
        data["task_id"] = resolved_task_id
    if total_steps is not None:
        data["total_steps"] = total_steps
    elif previous.get("total_steps") is not None:
        data["total_steps"] = previous.get("total_steps")
    if status in ("failed", "stopped"):
        data["failed_at"] = time.time()
        data["error_message"] = str(error_message) if error_message else previous.get("error_message", default_error_message)
        if error_traceback or previous.get("error_traceback"):
            data["error_traceback"] = str(error_traceback or previous.get("error_traceback"))
    atomic_write_json(PROCESS_STATUS, data)


def clear_task_status():
    if os.path.exists(PROCESS_STATUS):
        os.remove(PROCESS_STATUS)


def is_streamlit_control_exception(exc_type):
    return exc_type is not None and exc_type.__name__ in ("StopException", "RerunException")


def is_streamlit_control_traceback(status):
    error_traceback = str(status.get("error_traceback") or "")
    return "streamlit.runtime" in error_traceback and (
        "StopException" in error_traceback or "RerunException" in error_traceback
    )
