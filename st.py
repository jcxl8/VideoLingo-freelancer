import streamlit as st
import streamlit.components.v1 as components
import os, sys, re, shutil, time, json, html, subprocess, base64, hashlib, random
from core.st_utils.imports_and_utils import *
from core.st_utils.task_runner import TaskRunner
from core.st_utils.subtitle_preview_cache import ensure_preview
from core.st_utils.history_video import (
    find_project_original_videos,
    is_generated_video as _is_generated_video,
)
from core.st_utils.manual_merge_files import write_bytes_if_changed
from core.subtitle_proofread import load_subtitle_proofread_report
from core.st_utils.upload_copy import (
    consume_upload_copy_autogenerate_setting,
    render_upload_copy_suggestions,
    suppress_upload_copy_autogenerate_once,
)
from core.st_utils.retranslation import (
    clean_retranslation_outputs,
    get_current_translation_model as get_current_translation_model_from_profile,
    translation_profile_changed,
)
from core import *

# SET PATH
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['PATH'] += os.pathsep + current_dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="VideoLingo-Freelancer", page_icon="docs/logo.svg")

SUB_VIDEO = "output/output_sub.mp4"
DUB_VIDEO = "output/output_dub.mp4"
MANUAL_MERGE_DIR = "output/manual_merge"
MANUAL_CLEAR_REQUESTED = "manual_merge_cleanup_requested"
AMBIGUITY_REPORT = "output/log/ambiguity_report.json"
AMBIGUITY_REVIEW_FLAG = "output/.ambiguity_review_confirmed"
SUBTITLE_PROGRESS_HOST = None
SUBTITLE_PROCESSING_STEPS = [
    "WhisperX word-level transcription",
    "Sentence segmentation using NLP and LLM",
    "Summarization and multi-step translation",
    "Cutting and aligning long subtitles",
    "Generating timeline and subtitles",
    "Merging subtitles into the video",
]
TASK_RUNNER = TaskRunner(total_steps=len(SUBTITLE_PROCESSING_STEPS))
_SUBTITLE_PROGRESS_RENDER_SEQ = 0

_is_task_running = TASK_RUNNER.is_running
_read_task_status = TASK_RUNNER.read_status

def _format_duration(seconds):
    if seconds is None:
        return ""
    total_seconds = int(max(0, float(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}时{minutes:02d}分{seconds:02d}秒"

def _estimate_subtitle_remaining_time(status, current_step):
    return TASK_RUNNER.estimate_remaining_time(status, current_step, len(SUBTITLE_PROCESSING_STEPS))

def _format_eta_caption(status, current_step):
    remaining = _estimate_subtitle_remaining_time(status, current_step)
    if remaining is None:
        return None
    return f'{t("Estimated Remaining")}: {_format_duration(remaining)}'

def _total_elapsed_time(status):
    return TASK_RUNNER.total_elapsed_time(status)

def _render_step_list_html(rows, eta_seconds=None):
    list_html = "<br>".join(rows)
    eta_html = ""
    if eta_seconds is not None:
        eta_html = (
            f'<div style="margin-top:14px; color:#6B7280;">'
            f'{html.escape(t("Estimated Remaining"))}: '
            f'<span data-eta-seconds="{max(0, float(eta_seconds))}">{_format_duration(eta_seconds)}</span>'
            f'</div>'
        )
    step_list_height = max(110, len(rows) * 34 + (34 if eta_seconds is not None else 0) + 18)
    components.html(
        f"""
        <div style="font-size:20px; line-height:1.7; color:#31333F; font-family:system-ui, -apple-system, BlinkMacSystemFont, sans-serif;">
            {list_html}
            {eta_html}
        </div>
        <script>
        function formatDuration(totalSeconds) {{
            totalSeconds = Math.max(0, Math.floor(totalSeconds));
            const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, '0');
            const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0');
            const seconds = String(totalSeconds % 60).padStart(2, '0');
            return `${{hours}}时${{minutes}}分${{seconds}}秒`;
        }}
        function tickTimers() {{
            const now = Date.now() / 1000;
            document.querySelectorAll('[data-step-start]').forEach((el) => {{
                const start = Number(el.dataset.stepStart);
                if (!Number.isNaN(start)) {{
                    el.textContent = formatDuration(now - start);
                }}
            }});
            document.querySelectorAll('[data-eta-seconds]').forEach((el) => {{
                if (!el.dataset.etaStartedAt) {{
                    el.dataset.etaStartedAt = String(now);
                }}
                const startedAt = Number(el.dataset.etaStartedAt);
                const originalEta = Number(el.dataset.etaSeconds);
                if (!Number.isNaN(startedAt) && !Number.isNaN(originalEta)) {{
                    el.textContent = formatDuration(originalEta - (now - startedAt));
                }}
            }});
        }}
        tickTimers();
        setInterval(tickTimers, 1000);
        </script>
        """,
        height=step_list_height,
    )

def _next_subtitle_progress_render_id():
    global _SUBTITLE_PROGRESS_RENDER_SEQ
    _SUBTITLE_PROGRESS_RENDER_SEQ += 1
    return _SUBTITLE_PROGRESS_RENDER_SEQ

def _write_task_status(
    task_name,
    status="running",
    step_index=None,
    step_label=None,
    step_times=None,
    error_message=None,
    error_traceback=None,
):
    TASK_RUNNER.default_error_message = t("No detailed error was recorded for this older failure.")
    TASK_RUNNER.write_status(
        task_name,
        status=status,
        step_index=step_index,
        step_label=step_label,
        step_times=step_times,
        error_message=error_message,
        error_traceback=error_traceback,
    )

def _sync_task_status_with_runtime():
    return TASK_RUNNER.sync_status(
        stopped_message=t("The task process is no longer running. The GUI has refreshed to the latest stopped state."),
        refresh_message=t("The task was interrupted by a page refresh or Streamlit rerun. It has been unlocked and can continue from the stopped step."),
    )

def _task_guard(task_name, reset_status=True):
    TASK_RUNNER.default_error_message = t("No detailed error was recorded for this older failure.")
    if _is_task_running():
        raise RuntimeError(t("A task is already running. Please wait until it finishes."))

    def before_reset():
        if task_name == "subtitle":
            _clear_ambiguity_review_confirmed()
            _clear_ambiguity_report()

    return TASK_RUNNER.guard(
        task_name,
        reset_status=reset_status,
        before_reset=before_reset if task_name == "subtitle" else None,
        clear_status_on_success=task_name != "subtitle",
        streamlit_interrupted_message=t("The task was interrupted by a page refresh or Streamlit rerun. It has been unlocked and can continue from the stopped step."),
    )

def _render_subtitle_progress(host=None, current_step=None):
    if host is not None:
        host.empty()
    _sync_task_status_with_runtime()
    status = _read_task_status()
    if current_step is None:
        if status.get("task") != "subtitle" or status.get("status") not in ("running", "paused", "stopping", "failed", "stopped", "completed", "awaiting_review"):
            current_step = None
            status = {}
        else:
            current_step = status.get("step_index")

    current_step = int(current_step) if current_step is not None else None
    render_target = host if host is not None else st
    with render_target.container():
        rows = []
        step_times = status.get("step_times", {})
        now = time.time()
        eta_seconds = _estimate_subtitle_remaining_time(status, current_step)
        for index, step in enumerate(SUBTITLE_PROCESSING_STEPS, start=1):
            label = html.escape(t(step))
            timing = step_times.get(str(index), {})
            elapsed = timing.get("elapsed")
            if status.get("status") == "completed" or (current_step is not None and index < current_step):
                duration_text = f' （{t("Completed Status")}，{t("Elapsed")}：{_format_duration(elapsed)}）' if elapsed is not None else f' （{t("Completed Status")}）'
                rows.append(f'{index}. {label}{duration_text}')
            elif index == current_step:
                start_time = timing.get("start")
                if start_time:
                    running_elapsed = _format_duration(now - start_time)
                    timer = f'<span data-step-start="{start_time}">{running_elapsed}</span>'
                else:
                    timer = html.escape(t("Timing"))
                if status.get("status") == "paused":
                    state_label = t("Paused")
                elif status.get("status") == "stopping":
                    state_label = t("Stopping")
                else:
                    state_label = t("In Progress")
                rows.append(f'{index}. {label} <strong>（{state_label}，{t("Elapsed")}：{timer}）</strong>')
            else:
                rows.append(f'{index}. {label}')
        _render_step_list_html(rows, eta_seconds)

        if status.get("status") in ("failed", "stopped"):
            st.error(t("Subtitle processing failed. Please check the terminal logs."))
            step_label = status.get("step_label")
            if step_label:
                st.warning(f'{t("Stopped at step")}: {t(step_label)}')
            st.code(str(status.get("error_message") or t("No detailed error was recorded for this older failure.")), language="text")
            st.info(t("The task has stopped and is no longer locked. You can fix the issue and continue from the failed step."))
        elif status.get("status") == "completed":
            st.success(t("Subtitle processing complete! 🎉"))
            total_elapsed = _total_elapsed_time(status)
            if total_elapsed is not None:
                st.caption(f'{t("Total Elapsed")}: {_format_duration(total_elapsed)}')
        elif status.get("status") == "awaiting_review":
            if _has_ambiguity_items():
                st.info(t("Subtitle generation is complete. Please review the ambiguity report before merging subtitles into the video."))
            else:
                st.info(t("Subtitle generation is complete. No ambiguity report was generated. Please choose subtitle mode before merging subtitles into the video."))

        if current_step is not None:
            progress_value = 1.0 if status.get("status") == "completed" else min(max(current_step, 0), len(SUBTITLE_PROCESSING_STEPS)) / len(SUBTITLE_PROCESSING_STEPS)
            st.caption(f'{t("Progress")}: {progress_value:.0%}')
            st.progress(progress_value)
            if status.get("status") in ("running", "paused"):
                render_id = _next_subtitle_progress_render_id()
                control_cols = st.columns(2)
                if status.get("status") == "running":
                    if control_cols[0].button(t("Pause after current step"), key=f"pause_subtitle_task_{render_id}"):
                        TASK_RUNNER.request_pause("subtitle")
                        st.toast(t("Pause requested. The task will pause after the current step."), icon="⏸️")
                else:
                    if control_cols[0].button(t("Resume task"), key=f"resume_subtitle_task_{render_id}"):
                        TASK_RUNNER.resume("subtitle")
                        st.rerun()
                if control_cols[1].button(t("Stop after current step"), key=f"stop_subtitle_task_{render_id}"):
                    TASK_RUNNER.stop("subtitle", message=t("Stop requested. The task will stop after the current step."))
                    st.rerun()

def _run_subtitle_step(step_index, progress_host, step_key, callback):
    return TASK_RUNNER.run_step(
        "subtitle",
        step_index,
        step_key,
        callback,
        on_progress=lambda current_step: _render_subtitle_progress(progress_host, current_step),
    )

def _find_sub_video():
    if os.path.exists(SUB_VIDEO):
        return SUB_VIDEO
    if not os.path.isdir("output"):
        return None
    sub_video_pattern = re.compile(r"_sub(?:_v\d+)?\.mp4$")
    candidates = [
        os.path.join("output", name)
        for name in os.listdir("output")
        if sub_video_pattern.search(name) and not name.startswith("manual_")
    ]
    return max(candidates, key=os.path.getmtime) if candidates else None

def _subtitles_generated():
    if not os.path.isdir("output"):
        return False
    return any(
        name.endswith(".srt")
        for name in os.listdir("output")
    )

def _get_current_translation_model():
    """Return the current translation model name from config."""
    return get_current_translation_model_from_profile()

def _translation_model_changed():
    """Check if translation model differs from last completed translation."""
    return translation_profile_changed()

def _has_translation_results():
    return os.path.exists(os.path.join("output", "log", "translation_results.xlsx"))

def _render_retranslate_button(progress_host, controls_host=None, key_suffix="default", disabled=False):
    if not (_translation_model_changed() and _has_translation_results()):
        return False
    current_model = _get_current_translation_model()
    st.info(f'{t("Translation API profile changed. You can re-translate the current subtitles without re-running transcription.")} `{current_model}`')
    if st.button(
        f"🔄 {t('Re-translate current subtitles with')} {current_model}",
        key=f"retranslate_with_new_model_{key_suffix}",
        disabled=disabled,
        help=t("Only re-run translation, subtitle splitting, timestamp generation and optional video merge"),
    ):
        if controls_host is not None:
            controls_host.empty()
        clean_retranslation_outputs()
        with _task_guard("subtitle", reset_status=False):
            process_text(progress_host, start_step=3)
        st.rerun()
    return True

def _render_subtitle_outputs_without_video():
    _render_subtitle_proofread_report()
    _render_ambiguity_report()
    _render_open_output_button("open_output_after_subtitles")
    download_subtitle_zip_button(text=t("Download All Srt Files"))
    if load_key("enable_upload_copy_suggestions"):
        render_upload_copy_suggestions(_is_task_running)
    if st.button(t("Archive to 'history'"), key="cleanup_after_subtitle_generation"):
        st.session_state["last_text_archive_dir"] = cleanup()
        st.rerun()

def _render_merged_video_preview(video_path, key_prefix):
    if not video_path or not os.path.exists(video_path):
        return
    st.markdown(
        f"""
        <div style="margin: 18px 0 10px 0; padding: 10px 14px; border-radius: 6px; background: #E8F2FF; color: #174EA6; font-weight: 700;">
            {html.escape(t("Merged Video Preview"))}: <code>{html.escape(os.path.basename(video_path))}</code>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.video(video_path)

def _subtitle_mode_suffix(subtitle_mode):
    return _7_sub_into_vid.get_subtitle_mode_suffix(subtitle_mode)

def _manual_output_video_path(video_file, subtitle_mode, avoid_overwrite=False, output_dir=None):
    target_dir = output_dir or MANUAL_MERGE_DIR
    os.makedirs(target_dir, exist_ok=True)
    video_base = _7_sub_into_vid.get_video_base_name(video_file)
    language_pair = _7_sub_into_vid.get_language_pair_name()
    subtitle_suffix = _subtitle_mode_suffix(subtitle_mode)
    output_path = os.path.join(
        target_dir,
        f"manual_{video_base}_{language_pair}_{subtitle_suffix}_sub.mp4"
    )
    return _7_sub_into_vid.get_available_output_path(output_path) if avoid_overwrite else output_path

def _find_manual_output_video_path(video_file, subtitle_mode, output_dir=None):
    target_dir = output_dir or MANUAL_MERGE_DIR
    base_path = _manual_output_video_path(
        video_file,
        subtitle_mode,
        avoid_overwrite=False,
        output_dir=target_dir,
    )
    base, ext = os.path.splitext(base_path)
    candidates = []
    if os.path.exists(base_path):
        candidates.append(base_path)
    if os.path.isdir(target_dir):
        pattern = re.compile(rf"^{re.escape(os.path.basename(base))}_v\d+{re.escape(ext)}$")
        for name in os.listdir(target_dir):
            path = os.path.join(target_dir, name)
            if os.path.isfile(path) and pattern.match(name):
                candidates.append(path)
    return max(candidates, key=os.path.getmtime) if candidates else base_path

def _render_ambiguity_report():
    items = _read_ambiguity_items()
    items = [item for item in items if item.get("source")]
    if not items:
        return

    with st.expander(f'{t("Ambiguity Review Report")} ({len(items)})', expanded=False):
        st.caption(t("Please review these subtitle lines after generation. They may contain words or phrases with multiple possible meanings."))
        for index, item in enumerate(items, start=1):
            timestamp = item.get("timestamp") or t("Timestamp pending")
            subtitle_index = item.get("subtitle_index") or "?"
            st.markdown(
                f"**{index}. {t('Subtitle Index')} {subtitle_index} · {timestamp}**  \n"
                f"**{t('Source')}**: {item.get('source', '')}  \n"
                f"**{t('Translation')}**: {item.get('translation', '')}  \n"
                f"**{t('Ambiguity')}**: {item.get('ambiguity', '')}  \n"
                f"**{t('Reason')}**: {item.get('reason', '')}"
            )

def _render_subtitle_proofread_report():
    report = load_subtitle_proofread_report()
    if not report:
        return
    summary = report.get("summary", {})
    issues = report.get("issues", [])
    if report.get("status") == "passed":
        st.success(
            f'{t("Subtitle proofreading passed")} · '
            f'{summary.get("entry_count", 0)} {t("subtitle entries")}'
        )
        return
    st.warning(
        f'{t("Subtitle proofreading found issues")} · '
        f'{summary.get("error_count", 0)} {t("errors")}, '
        f'{summary.get("warning_count", 0)} {t("warnings")}'
    )
    with st.expander(f'{t("Subtitle Proofread Report")} ({len(issues)})', expanded=True):
        st.caption(t("The report does not modify subtitle files. Please verify flagged passages before merging."))
        for position, item in enumerate(issues, 1):
            location = item.get("entry_index") or "—"
            timestamp = item.get("timestamp") or "—"
            st.markdown(
                f'**{position}. [{str(item.get("severity", "warning")).upper()}] '
                f'{t(item.get("type", ""))} · {t("Subtitle Index")} {location} · {timestamp}**  \n'
                f'**{t("Reason")}**: {t(item.get("reason", ""))}  \n'
                f'**{t("Source")}**: {item.get("source", "—")}  \n'
                f'**{t("Translation")}**: {item.get("translation", "—")}'
            )

def _read_ambiguity_items():
    if not os.path.exists(AMBIGUITY_REPORT):
        return []
    try:
        with open(AMBIGUITY_REPORT, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception:
        return []
    return items if isinstance(items, list) else []

def _has_ambiguity_items():
    return any(item.get("source") for item in _read_ambiguity_items())

def _ambiguity_review_confirmed():
    return os.path.exists(AMBIGUITY_REVIEW_FLAG)

def _mark_ambiguity_review_confirmed():
    os.makedirs(os.path.dirname(AMBIGUITY_REVIEW_FLAG), exist_ok=True)
    with open(AMBIGUITY_REVIEW_FLAG, "w", encoding="utf-8") as f:
        f.write(str(time.time()))

def _clear_ambiguity_review_confirmed():
    if os.path.exists(AMBIGUITY_REVIEW_FLAG):
        os.remove(AMBIGUITY_REVIEW_FLAG)

def _clear_ambiguity_report():
    for path in (AMBIGUITY_REPORT, "output/ambiguity_report.md"):
        if os.path.exists(path):
            os.remove(path)

def _subtitle_review_pending():
    status = _read_task_status()
    return (
        status.get("task") == "subtitle"
        and status.get("status") == "awaiting_review"
        and load_key("burn_subtitles")
        and not _find_sub_video()
    )

def _open_archived_dir(path):
    if not path or not os.path.isdir(path):
        return False
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif os.name == "nt":
        os.startfile(path)
    else:
        subprocess.Popen(["xdg-open", path])
    return True

def _render_archived_dir_button(session_key):
    archived_dir = st.session_state.get(session_key)
    if not archived_dir:
        return
    st.success(f'{t("Archived to")}: {archived_dir}')
    if st.button(t("Open Archived Folder"), key=f"open_{session_key}"):
        if not _open_archived_dir(archived_dir):
            st.error(t("Archived folder not found"))

def _render_open_output_button(key):
    if st.button(t("Open Subtitle Folder"), key=key):
        if not _open_archived_dir(os.path.abspath("output")):
            st.error(t("Subtitle folder not found"))

def _safe_uploaded_name(name):
    raw_name = name.replace(' ', '_')
    base, ext = os.path.splitext(raw_name)
    return re.sub(r'[^\w\-_\.]', '', base) + ext.lower()

def _save_uploaded_file(uploaded_file, target_name):
    os.makedirs(MANUAL_MERGE_DIR, exist_ok=True)
    path = os.path.join(MANUAL_MERGE_DIR, target_name)
    write_bytes_if_changed(path, uploaded_file.getbuffer())
    return path


def _request_manual_merge_cleanup():
    st.session_state[MANUAL_CLEAR_REQUESTED] = True


def _consume_manual_merge_cleanup_request():
    if not st.session_state.pop(MANUAL_CLEAR_REQUESTED, False):
        return False
    if os.path.isdir(MANUAL_MERGE_DIR):
        shutil.rmtree(MANUAL_MERGE_DIR)
    for key in (
        "manual_video_source",
        "manual_video_upload",
        "manual_src_srt",
        "manual_trans_srt",
        "manual_bilingual_srt",
        "manual_history_project",
        "manual_history_video_file",
        "manual_subtitle_mode",
        "last_manual_merged_video",
    ):
        st.session_state.pop(key, None)
    return True

def _allowed_video_exts():
    return tuple(f".{ext.lower()}" for ext in load_key("allowed_video_formats"))

def _find_history_projects():
    allowed_exts = _allowed_video_exts()
    history_dir = "history"
    projects = []
    if not os.path.isdir(history_dir):
        return projects
    for root, _, files in os.walk(history_dir):
        video_files = [
            os.path.join(root, filename)
            for filename in files
            if filename.lower().endswith(allowed_exts)
        ]
        if video_files:
            projects.append((max(os.path.getmtime(path) for path in video_files), root))
    return [path for _, path in sorted(projects, reverse=True)]

def _find_history_project_videos(project_dir):
    return find_project_original_videos(project_dir, _allowed_video_exts())

def _find_history_videos():
    allowed_exts = tuple(f".{ext.lower()}" for ext in load_key("allowed_video_formats"))
    history_dir = "history"
    videos = []
    if not os.path.isdir(history_dir):
        return videos
    for root, _, files in os.walk(history_dir):
        for filename in files:
            if filename.lower().endswith(allowed_exts) and not _is_generated_video(filename):
                path = os.path.join(root, filename)
                videos.append(path)
    return sorted(videos, key=os.path.getmtime, reverse=True)

def _format_history_project(project_dir):
    return os.path.relpath(project_dir, "history")

def _format_history_video(video_path):
    status = t("Merged subtitle video") if _is_generated_video(video_path) else t("Original video")
    return f"{status} - {os.path.basename(video_path)}"

def _find_history_subtitle_file(project_dir, video_path, subtitle_key):
    if not project_dir:
        return None

    legacy_name = f"{subtitle_key}.srt"
    legacy_path = os.path.join(project_dir, legacy_name)
    subtitle_base = _7_sub_into_vid.get_subtitle_base_name(video_path) if video_path else None
    candidates = []
    if subtitle_base:
        candidates.append(os.path.join(project_dir, f"{subtitle_base}_{subtitle_key}.srt"))
    candidates.append(legacy_path)
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    srt_files = [
        os.path.join(project_dir, name)
        for name in os.listdir(project_dir)
        if name.lower().endswith(".srt")
    ]
    if subtitle_key in ("src_trans", "trans_src"):
        suffix = f"_{subtitle_key}.srt"
        matches = [path for path in srt_files if os.path.basename(path).endswith(suffix)]
    elif subtitle_key == "src":
        matches = [
            path for path in srt_files
            if os.path.basename(path).endswith("_src.srt")
            and not os.path.basename(path).endswith("_trans_src.srt")
        ]
    else:
        matches = [
            path for path in srt_files
            if os.path.basename(path).endswith("_trans.srt")
            and not os.path.basename(path).endswith("_src_trans.srt")
        ]
    return sorted(matches, key=os.path.getmtime, reverse=True)[0] if matches else None

def _get_history_subtitle_paths(project_dir, video_path, subtitle_mode):
    if not project_dir:
        return None, None, []

    src_srt_path = _find_history_subtitle_file(project_dir, video_path, "src")
    trans_srt_path = _find_history_subtitle_file(project_dir, video_path, "trans")
    src_trans_srt = _find_history_subtitle_file(project_dir, video_path, "src_trans")
    trans_src_srt = _find_history_subtitle_file(project_dir, video_path, "trans_src")

    def split_history_bilingual(srt_path, first_line):
        os.makedirs(MANUAL_MERGE_DIR, exist_ok=True)
        src_out = os.path.join(MANUAL_MERGE_DIR, "manual_history_src.srt")
        trans_out = os.path.join(MANUAL_MERGE_DIR, "manual_history_trans.srt")
        _split_bilingual_srt(srt_path, trans_out, src_out, first_line=first_line)
        return src_out, trans_out, [os.path.basename(srt_path)]

    if subtitle_mode == "source_only":
        return src_srt_path, None, [os.path.basename(src_srt_path)] if src_srt_path else ["src.srt"]

    if subtitle_mode == "translation_only":
        return None, trans_srt_path, [os.path.basename(trans_srt_path)] if trans_srt_path else ["trans.srt"]

    if subtitle_mode == "bilingual_src_top":
        if src_trans_srt:
            return split_history_bilingual(src_trans_srt, first_line="src")
        return (
            src_srt_path,
            trans_srt_path,
            [os.path.basename(path) for path in (src_srt_path, trans_srt_path) if path],
        )

    if subtitle_mode in ("bilingual_trans_top", "single_bilingual_trans_top"):
        if trans_src_srt:
            return split_history_bilingual(trans_src_srt, first_line="trans")
        return (
            src_srt_path,
            trans_srt_path,
            [os.path.basename(path) for path in (src_srt_path, trans_srt_path) if path],
        )

    return None, None, []

def _show_history_subtitle_status(src_srt, trans_srt, need_src, need_trans, need_single_bilingual, display_files=None):
    display_files = display_files or []
    if display_files:
        st.caption(f'{t("Matched history subtitle files")}: ' + " | ".join(f"`{item}`" for item in display_files))

    linked = []
    if src_srt:
        linked.append(f'{t("Source subtitle")}: `{os.path.basename(src_srt)}`')
    if trans_srt:
        linked.append(f'{t("Translated subtitle")}: `{os.path.basename(trans_srt)}`')
    if linked:
        st.caption(f'{t("Using history subtitle files")}: ' + " | ".join(linked))

    missing = []
    if need_src and not src_srt:
        missing.append("src.srt")
    if need_trans and not trans_srt:
        missing.append("trans.srt")
    if need_single_bilingual and (not src_srt or not trans_srt):
        missing.append("trans_src.srt / src.srt + trans.srt")
    if missing:
        st.error(f'{t("Missing history subtitle files")}: {", ".join(missing)}')

def _split_bilingual_srt(srt_path, trans_out, src_out, first_line="trans"):
    with open(srt_path, "r", encoding="utf-8-sig") as f:
        blocks = re.split(r"\n\s*\n", f.read().strip())

    trans_blocks = []
    src_blocks = []
    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if len(lines) < 4:
            continue
        index, timestamp = lines[0], lines[1]
        text_lines = lines[2:]
        first_text = text_lines[0]
        second_text = " ".join(text_lines[1:]).strip()
        if first_line == "src":
            src_text = first_text
            trans_text = second_text
        else:
            trans_text = first_text
            src_text = second_text
        if not src_text:
            src_text = trans_text
        if not trans_text:
            trans_text = src_text
        trans_blocks.append(f"{index}\n{timestamp}\n{trans_text}")
        src_blocks.append(f"{index}\n{timestamp}\n{src_text}")

    write_bytes_if_changed(trans_out, "\n\n".join(trans_blocks).encode("utf-8"))
    write_bytes_if_changed(src_out, "\n\n".join(src_blocks).encode("utf-8"))

def _parse_srt_file(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        content = f.read().strip()
    if not content:
        return []
    entries = []
    for block in re.split(r"\n\s*\n", content):
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        entries.append({
            "index": lines[0],
            "timestamp": lines[1],
            "text": "\n".join(lines[2:]).strip(),
            "text_lines": lines[2:],
        })
    return entries

def _write_srt_file(path, entries):
    blocks = []
    for position, entry in enumerate(entries, start=1):
        index = entry.get("index") or str(position)
        timestamp = entry.get("timestamp", "")
        text = str(entry.get("text", "")).strip()
        blocks.append(f"{index}\n{timestamp}\n{text}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(blocks).strip() + "\n")

def _split_bilingual_entries(entries, first_line="trans"):
    src_entries = []
    trans_entries = []
    for entry in entries:
        text_lines = entry.get("text_lines") or str(entry.get("text", "")).splitlines()
        if not text_lines:
            continue
        first_text = text_lines[0].strip()
        second_text = "\n".join(text_lines[1:]).strip()
        if first_line == "src":
            src_text = first_text
            trans_text = second_text
        else:
            trans_text = first_text
            src_text = second_text
        src_entries.append({**entry, "text": src_text or trans_text})
        trans_entries.append({**entry, "text": trans_text or src_text})
    return src_entries, trans_entries

def _write_bilingual_srt(path, src_entries, trans_entries, first_line="trans"):
    count = min(len(src_entries), len(trans_entries))
    blocks = []
    for position in range(count):
        src_entry = src_entries[position]
        trans_entry = trans_entries[position]
        index = src_entry.get("index") or trans_entry.get("index") or str(position + 1)
        timestamp = src_entry.get("timestamp") or trans_entry.get("timestamp") or ""
        src_text = str(src_entry.get("text", "")).strip()
        trans_text = str(trans_entry.get("text", "")).strip()
        if first_line == "src":
            text = f"{src_text}\n{trans_text}"
        else:
            text = f"{trans_text}\n{src_text}"
        blocks.append(f"{index}\n{timestamp}\n{text}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(blocks).strip() + "\n")

def _srt_timestamp_start_seconds(timestamp):
    match = re.search(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", str(timestamp))
    if not match:
        return 1.0
    hours, minutes, seconds, milliseconds = [int(part) for part in match.groups()]
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000

def _srt_timestamp_midpoint_seconds(timestamp):
    matches = re.findall(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", str(timestamp))
    if not matches:
        return 1.0
    values = []
    for match in matches[:2]:
        hours, minutes, seconds, milliseconds = [int(part) for part in match]
        values.append(hours * 3600 + minutes * 60 + seconds + milliseconds / 1000)
    if len(values) == 1:
        return values[0] + 0.2
    return values[0] + max(0.2, (values[1] - values[0]) * 0.45)

def _preview_seek_time(src_srt=None, trans_srt=None):
    all_entries = []
    for path in (trans_srt, src_srt):
        entries = _parse_srt_file(path)
        if entries:
            all_entries.extend(entries)
    if all_entries:
        first_safe_index = max(0, int(len(all_entries) * 0.10))
        last_safe_index = max(first_safe_index + 1, int(len(all_entries) * 0.90))
        candidates = [
            entry for entry in all_entries[first_safe_index:last_safe_index]
            if _srt_timestamp_start_seconds(entry.get("timestamp", "")) >= 5.0
        ]
        if not candidates:
            candidates = all_entries[first_safe_index:last_safe_index] or all_entries
        return _srt_timestamp_midpoint_seconds(random.choice(candidates).get("timestamp", ""))
    return 1.0

def _subtitle_preview_config_stamp():
    keys = [
        "subtitle_layout",
        "subtitle_layout_profile",
        "subtitle_hardsub_strategy",
        "watermark_enabled",
        "portrait_source_font_size",
        "portrait_translation_font_size",
        "portrait_hardsub_translation_font_size",
        "portrait_bilingual_offset",
        "portrait_hardsub_translation_offset",
        "portrait_watermark_font_size",
        "portrait_watermark_offset",
        "landscape_hardsub_translation_offset",
        "landscape_bilingual_translation_offset",
        "landscape_source_font_size",
        "landscape_translation_font_size",
        "landscape_watermark_font_size",
        "landscape_watermark_offset",
    ]
    parts = [f"style_version={getattr(_7_sub_into_vid, 'SUBTITLE_STYLE_VERSION', 1)}"]
    for key in keys:
        try:
            value = load_key(key)
        except Exception:
            value = ""
        parts.append(f"{key}={value}")
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]

def _generated_preview_path(video_file, subtitle_mode):
    subtitle_paths = _7_sub_into_vid.get_default_subtitle_paths(video_file)
    file_parts = []
    for path in list(subtitle_paths.values()) + ([video_file] if video_file else []):
        if path and os.path.exists(path):
            stat = os.stat(path)
            file_parts.append(f"{path}:{stat.st_mtime_ns}:{stat.st_size}")
    stamp = hashlib.sha1("|".join(file_parts).encode("utf-8")).hexdigest()[:10] if file_parts else str(int(time.time()))
    config_stamp = _subtitle_preview_config_stamp()
    os.makedirs(MANUAL_MERGE_DIR, exist_ok=True)
    return os.path.join(MANUAL_MERGE_DIR, f"preview_{subtitle_mode}_{stamp}_{config_stamp}.jpg")

def _manual_preview_path(video_file, subtitle_mode, src_srt=None, trans_srt=None):
    paths = [path for path in (video_file, src_srt, trans_srt) if path and os.path.exists(path)]
    file_parts = []
    for path in paths:
        stat = os.stat(path)
        file_parts.append(f"{path}:{stat.st_mtime_ns}:{stat.st_size}")
    stamp = hashlib.sha1("|".join(file_parts).encode("utf-8")).hexdigest()[:10] if file_parts else str(int(time.time()))
    config_stamp = _subtitle_preview_config_stamp()
    video_base = _7_sub_into_vid.get_video_base_name(video_file) if video_file else "manual"
    os.makedirs(MANUAL_MERGE_DIR, exist_ok=True)
    return os.path.join(MANUAL_MERGE_DIR, f"preview_manual_{video_base}_{subtitle_mode}_{stamp}_{config_stamp}.jpg")

def _render_preview_image(path):
    if not path or not os.path.exists(path):
        return
    with open(path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("ascii")
    st.markdown(
        f"""
        <figure style="margin: 12px 0 0 0; width: 100%;">
            <figcaption style="margin:0 0 8px 0;color:#6B7280;font-size:16px;text-align:center;font-weight:600;">
                {html.escape(t("Subtitle Preview"))}
            </figcaption>
            <img
                src="data:image/jpeg;base64,{image_data}"
                alt="{html.escape(t("Subtitle Preview"))}"
                style="display:block;width:100%;height:auto;border-radius:6px;"
            />
        </figure>
        """,
        unsafe_allow_html=True,
    )

def _render_subtitle_preview(video_file, src_srt, trans_srt, subtitle_mode, preview_path):
    if not video_file:
        return

    def render_preview():
        with st.spinner(t("Generating subtitle preview...")):
            _7_sub_into_vid.render_subtitle_preview_frame(
                video_file=video_file,
                output_image=preview_path,
                src_srt=src_srt,
                trans_srt=trans_srt,
                subtitle_mode=subtitle_mode,
                seek_time=_preview_seek_time(src_srt, trans_srt),
                watermark_enabled=load_key("watermark_enabled"),
            )

    ensure_preview(preview_path, render_preview)
    _render_preview_image(preview_path)

def _render_generated_subtitle_preview(subtitle_mode, subtitle_ready):
    if not subtitle_ready:
        return
    try:
        video_file, src_srt, trans_srt, _, _ = _prepare_generated_subtitle_inputs(subtitle_mode, sync=False)
        preview_path = _generated_preview_path(video_file, subtitle_mode)
    except Exception as exc:
        st.error(str(exc))
        return

    _render_subtitle_preview(video_file, src_srt, trans_srt, subtitle_mode, preview_path)

def _sync_generated_subtitle_files(video_file=None, write=False):
    if video_file is None:
        video_file = _1_ytdlp.find_video_files()
    subtitle_paths = _7_sub_into_vid.get_default_subtitle_paths(video_file)
    existing = {
        key: path
        for key, path in subtitle_paths.items()
        if os.path.exists(path)
    }
    if len(existing) < 2:
        return None

    latest_key, latest_path = max(existing.items(), key=lambda item: os.path.getmtime(item[1]))
    if not write:
        return latest_path

    if latest_key in ("trans_src", "src_trans"):
        latest_entries = _parse_srt_file(latest_path)
        src_entries, trans_entries = _split_bilingual_entries(
            latest_entries,
            first_line="trans" if latest_key == "trans_src" else "src",
        )
    else:
        src_entries = _parse_srt_file(subtitle_paths["src"])
        trans_entries = _parse_srt_file(subtitle_paths["trans"])

    if not src_entries or not trans_entries:
        return latest_path

    count = min(len(src_entries), len(trans_entries))
    src_entries = src_entries[:count]
    trans_entries = trans_entries[:count]
    _write_srt_file(subtitle_paths["src"], src_entries)
    _write_srt_file(subtitle_paths["trans"], trans_entries)
    _write_bilingual_srt(subtitle_paths["src_trans"], src_entries, trans_entries, first_line="src")
    _write_bilingual_srt(subtitle_paths["trans_src"], src_entries, trans_entries, first_line="trans")
    return latest_path

def _subtitle_mode_options():
    return {
        t("Bilingual: translation above source"): "bilingual_trans_top",
        t("Bilingual: source above translation"): "bilingual_src_top",
        t("Only translated subtitles"): "translation_only",
        t("Only source subtitles"): "source_only",
    }

def _prepare_generated_subtitle_inputs(subtitle_mode, sync=False):
    video_file = _1_ytdlp.find_video_files()
    sync_source = _sync_generated_subtitle_files(video_file, write=sync)
    subtitle_paths = _7_sub_into_vid.get_default_subtitle_paths(video_file)
    src_srt = subtitle_paths["src"]
    trans_srt = subtitle_paths["trans"]
    used_files = []

    if subtitle_mode == "bilingual_trans_top" and os.path.exists(subtitle_paths["trans_src"]):
        os.makedirs(MANUAL_MERGE_DIR, exist_ok=True)
        src_srt = os.path.join(MANUAL_MERGE_DIR, "generated_review_src.srt")
        trans_srt = os.path.join(MANUAL_MERGE_DIR, "generated_review_trans.srt")
        _split_bilingual_srt(subtitle_paths["trans_src"], trans_srt, src_srt, first_line="trans")
        used_files.append(subtitle_paths["trans_src"])
    elif subtitle_mode == "bilingual_src_top" and os.path.exists(subtitle_paths["src_trans"]):
        os.makedirs(MANUAL_MERGE_DIR, exist_ok=True)
        src_srt = os.path.join(MANUAL_MERGE_DIR, "generated_review_src.srt")
        trans_srt = os.path.join(MANUAL_MERGE_DIR, "generated_review_trans.srt")
        _split_bilingual_srt(subtitle_paths["src_trans"], trans_srt, src_srt, first_line="src")
        used_files.append(subtitle_paths["src_trans"])
    else:
        if subtitle_mode in ("source_only", "bilingual_src_top", "bilingual_trans_top"):
            used_files.append(src_srt)
        if subtitle_mode in ("translation_only", "bilingual_src_top", "bilingual_trans_top"):
            used_files.append(trans_srt)

    missing = []
    if subtitle_mode == "source_only" and not os.path.exists(src_srt):
        missing.append(src_srt)
    elif subtitle_mode == "translation_only" and not os.path.exists(trans_srt):
        missing.append(trans_srt)
    elif subtitle_mode.startswith("bilingual"):
        for path in (src_srt, trans_srt):
            if not os.path.exists(path):
                missing.append(path)
    if missing:
        raise FileNotFoundError(f"Subtitle file not found: {', '.join(missing)}")

    return video_file, src_srt, trans_srt, used_files, sync_source

def _render_generated_merge_choice():
    subtitle_modes = _subtitle_mode_options()
    labels = list(subtitle_modes.keys())
    mode_label = st.selectbox(t("Subtitle Mode"), labels, key="generated_subtitle_mode")
    subtitle_mode = subtitle_modes[mode_label]
    try:
        _, _, _, used_files, sync_source = _prepare_generated_subtitle_inputs(subtitle_mode, sync=False)
    except Exception as exc:
        st.error(str(exc))
        return subtitle_mode, False
    if sync_source:
        st.caption(f'{t("Synced subtitle files from")}: `{os.path.basename(sync_source)}`')
    if used_files:
        st.caption(f'{t("Using subtitle files")}: ' + " | ".join(f"`{os.path.basename(path)}`" for path in used_files))
    _render_generated_subtitle_preview(subtitle_mode, True)
    return subtitle_mode, True

def manual_subtitle_merge_section():
    st.header(t("c. Manually Merge Subtitles"))
    if _consume_manual_merge_cleanup_request():
        st.rerun()
    with st.container(border=True):
        video_source = st.radio(
            t("Video Source"),
            [t("Upload Video"), t("Use History Video")],
            horizontal=True,
            key="manual_video_source"
        )

        selected_video = None
        selected_project = None
        using_history_video = video_source == t("Use History Video")
        if video_source == t("Upload Video"):
            uploaded_video = st.file_uploader(
                t("Add video"),
                type=load_key("allowed_video_formats"),
                key="manual_video_upload"
            )
            if uploaded_video:
                selected_video = _save_uploaded_file(uploaded_video, _safe_uploaded_name(uploaded_video.name))
        else:
            history_projects = _find_history_projects()
            if history_projects:
                selected_project = st.selectbox(
                    t("Select history project"),
                    history_projects,
                    format_func=_format_history_project,
                    key="manual_history_project"
                )
                if st.button(
                    t("Open Project Folder"),
                    key="open_manual_history_project_folder",
                    width="stretch",
                ):
                    if not _open_archived_dir(os.path.abspath(selected_project)):
                        st.error(t("Project folder not found"))
                history_videos = _find_history_project_videos(selected_project)
                if history_videos:
                    selected_video = st.selectbox(
                        t("Select history video file"),
                        history_videos,
                        index=0,
                        format_func=_format_history_video,
                        key="manual_history_video_file"
                    )
                else:
                    st.error(t("No original video found in this history project"))
            else:
                st.info(t("No history videos found"))

        if selected_video and os.path.exists(selected_video):
            st.video(selected_video)

        subtitle_modes = {
            t("Only translated subtitles"): "translation_only",
            t("Only source subtitles"): "source_only",
            t("Bilingual: source above translation"): "bilingual_src_top",
            t("Bilingual: translation above source"): "bilingual_trans_top",
            t("Single bilingual SRT: translation above source"): "single_bilingual_trans_top",
        }
        mode_label = st.selectbox(t("Subtitle Mode"), list(subtitle_modes.keys()), key="manual_subtitle_mode")
        subtitle_mode = subtitle_modes[mode_label]

        src_srt = None
        trans_srt = None
        need_src = subtitle_mode in ("source_only", "bilingual_src_top", "bilingual_trans_top")
        need_trans = subtitle_mode in ("translation_only", "bilingual_src_top", "bilingual_trans_top")
        need_single_bilingual = subtitle_mode == "single_bilingual_trans_top"

        if using_history_video:
            src_srt, trans_srt, matched_subtitle_files = _get_history_subtitle_paths(selected_project, selected_video, subtitle_mode)
            _show_history_subtitle_status(src_srt, trans_srt, need_src, need_trans, need_single_bilingual, matched_subtitle_files)
        else:
            c1, c2 = st.columns(2)
            with c1:
                if need_src:
                    uploaded_src = st.file_uploader(t("Add source subtitle"), type=["srt"], key="manual_src_srt")
                    if uploaded_src:
                        src_srt = _save_uploaded_file(uploaded_src, "manual_src.srt")
                elif need_single_bilingual:
                    uploaded_bilingual = st.file_uploader(t("Add bilingual subtitle"), type=["srt"], key="manual_bilingual_srt")
                    if uploaded_bilingual:
                        bilingual_srt = _save_uploaded_file(uploaded_bilingual, "manual_bilingual.srt")
                        src_srt = os.path.join(MANUAL_MERGE_DIR, "manual_src.srt")
                        trans_srt = os.path.join(MANUAL_MERGE_DIR, "manual_trans.srt")
                        _split_bilingual_srt(bilingual_srt, trans_srt, src_srt)
            with c2:
                if need_trans:
                    uploaded_trans = st.file_uploader(t("Add translated subtitle"), type=["srt"], key="manual_trans_srt")
                    if uploaded_trans:
                        trans_srt = _save_uploaded_file(uploaded_trans, "manual_trans.srt")

        preview_subtitle_mode = "bilingual_trans_top" if need_single_bilingual else subtitle_mode
        preview_ready = (
            selected_video
            and os.path.exists(selected_video)
            and (
                (preview_subtitle_mode == "source_only" and src_srt and os.path.exists(src_srt))
                or (preview_subtitle_mode == "translation_only" and trans_srt and os.path.exists(trans_srt))
                or (preview_subtitle_mode.startswith("bilingual") and src_srt and trans_srt and os.path.exists(src_srt) and os.path.exists(trans_srt))
            )
        )
        if preview_ready:
            preview_path = _manual_preview_path(selected_video, preview_subtitle_mode, src_srt, trans_srt)
            _render_subtitle_preview(
                selected_video,
                src_srt,
                trans_srt,
                preview_subtitle_mode,
                preview_path,
            )

        manual_output_dir = (
            os.path.abspath(selected_project) if using_history_video and selected_project
            else MANUAL_MERGE_DIR
        )
        manual_output_video = (
            _find_manual_output_video_path(
                selected_video,
                subtitle_mode,
                output_dir=manual_output_dir,
            )
            if selected_video else None
        )
        button_disabled = _is_task_running()
        if st.button(t("Merge Selected Video and Subtitles"), key="manual_merge_button", width="stretch", disabled=button_disabled):
            if not selected_video:
                st.error(t("Please add or select a video first"))
            elif need_single_bilingual and (not src_srt or not trans_srt):
                st.error(t("Please add bilingual subtitle first"))
            elif need_src and not src_srt:
                st.error(t("Please add source subtitle first"))
            elif need_trans and not trans_srt:
                st.error(t("Please add translated subtitle first"))
            else:
                with _task_guard("manual_merge"):
                    with st.spinner(t("Merging subtitles to video...")):
                        merge_output_video = _manual_output_video_path(
                            selected_video,
                            subtitle_mode,
                            avoid_overwrite=True,
                            output_dir=manual_output_dir,
                        )
                        merged_video = _7_sub_into_vid.burn_subtitles_to_video(
                            video_file=selected_video,
                            output_video=merge_output_video,
                            src_srt=src_srt,
                            trans_srt=trans_srt,
                            subtitle_mode="bilingual_trans_top" if need_single_bilingual else subtitle_mode,
                        )
                        st.session_state["last_manual_merged_video"] = merged_video
                st.success(t("Manual subtitle merge complete"))
                st.rerun()
        elif button_disabled:
            st.info(t("A task is already running. Please wait until it finishes."))

        if manual_output_video and os.path.exists(manual_output_video):
            last_manual_video = st.session_state.get("last_manual_merged_video")
            last_manual_matches_project = (
                last_manual_video
                and os.path.exists(last_manual_video)
                and os.path.dirname(os.path.abspath(last_manual_video))
                == os.path.abspath(manual_output_dir)
            )
            manual_preview_video = last_manual_video if last_manual_matches_project else manual_output_video
            _render_merged_video_preview(manual_preview_video, "manual")
            download_video_path = manual_preview_video if os.path.exists(manual_preview_video) else manual_output_video
            with open(download_video_path, "rb") as f:
                st.download_button(
                    t("Download Merged Video"),
                    data=f,
                    file_name=os.path.basename(download_video_path),
                    mime="video/mp4",
                    key="manual_download_video"
                )
            if using_history_video and selected_project:
                if st.button(
                    t("Open Project Folder"),
                    key="open_manual_result_project_folder",
                    width="stretch",
                ):
                    if not _open_archived_dir(os.path.abspath(selected_project)):
                        st.error(t("Project folder not found"))

        if os.path.isdir(MANUAL_MERGE_DIR):
            st.button(
                t("Clear Manual Merge Files"),
                key="manual_clear_button",
                on_click=_request_manual_merge_cleanup,
            )

def text_processing_section():
    global SUBTITLE_PROGRESS_HOST
    _sync_task_status_with_runtime()
    st.header(t("b. Translate and Generate Subtitles"))

    # Handle standalone ambiguity check trigger from sidebar button
    if st.session_state.get("trigger_ambiguity_check") and not _is_task_running():
        st.session_state["trigger_ambiguity_check"] = False
        with st.spinner(t("Running ambiguity check... This may take a few minutes.")):
            try:
                from core.translate_lines import generate_ambiguity_report_standalone
                success = generate_ambiguity_report_standalone()
                if success:
                    st.toast(t("Ambiguity report generated!"), icon="✅")
                else:
                    st.toast(t("Ambiguity check failed. See server log for details."), icon="❌")
            except Exception as e:
                st.toast(f"{t('Ambiguity check error: ')}{e}", icon="❌")
        st.rerun()

    with st.container(border=True):
        st.markdown(f"""
        <p style='font-size: 20px;'>
        {t("This stage includes the following steps:")}
        """, unsafe_allow_html=True)

        SUBTITLE_PROGRESS_HOST = st.empty()
        _render_subtitle_progress(SUBTITLE_PROGRESS_HOST)
        _render_archived_dir_button("last_text_archive_dir")

        sub_video = _find_sub_video()
        if _subtitle_review_pending():
            _render_subtitle_proofread_report()
            if _has_ambiguity_items():
                st.warning(t("Ambiguity review is pending. Please confirm before merging subtitles into the video."))
                _render_ambiguity_report()
            else:
                st.info(t("Subtitle generation is complete. Please choose subtitle mode before merging subtitles into the video."))
            _render_open_output_button("open_output_before_merge")
            if _render_retranslate_button(SUBTITLE_PROGRESS_HOST, key_suffix="awaiting_review", disabled=_is_task_running()):
                return True
            selected_subtitle_mode, subtitle_ready = _render_generated_merge_choice()
            if st.button(t("I have reviewed it, continue merging video"), key="continue_merge_after_ambiguity_review", disabled=_is_task_running() or not subtitle_ready):
                _mark_ambiguity_review_confirmed()
                try:
                    with _task_guard("subtitle", reset_status=False):
                        process_subtitle_merge(SUBTITLE_PROGRESS_HOST, selected_subtitle_mode)
                finally:
                    _clear_ambiguity_review_confirmed()
                st.rerun()
            return True

        if not sub_video:
            status = _read_task_status()
            if status.get("task") == "subtitle" and status.get("status") == "completed" and _subtitles_generated():
                _render_subtitle_outputs_without_video()
                return True
            if maybe_auto_process_after_download():
                return True
            button_disabled = _is_task_running()
            controls_host = st.empty()
            with controls_host.container():
                if button_disabled:
                    st.caption(t("A task is already running. Please wait until it finishes."))
                if status.get("task") == "subtitle" and status.get("status") in ("failed", "stopped"):
                    failed_step = int(status.get("step_index") or 1)
                    failed_label = status.get("step_label") or SUBTITLE_PROCESSING_STEPS[min(max(failed_step, 1), len(SUBTITLE_PROCESSING_STEPS)) - 1]
                    if st.button(
                        f'{t("Continue from failed step")}: {failed_step}. {t(failed_label)}',
                        key="continue_failed_subtitle_step",
                        disabled=button_disabled,
                    ):
                        controls_host.empty()
                        with _task_guard("subtitle", reset_status=False):
                            process_text(SUBTITLE_PROGRESS_HOST, start_step=failed_step)
                        st.rerun()
                _render_retranslate_button(SUBTITLE_PROGRESS_HOST, controls_host, key_suffix="no_video", disabled=button_disabled)
                if st.button(t("Start Processing Subtitles"), key="text_processing_button", disabled=button_disabled):
                    controls_host.empty()
                    with _task_guard("subtitle"):
                        process_text(SUBTITLE_PROGRESS_HOST)
                    st.rerun()
        else:
            _render_subtitle_proofread_report()
            _render_ambiguity_report()
            if load_key("burn_subtitles"):
                _render_merged_video_preview(st.session_state.get("last_text_merged_video") or sub_video, "text")
            if _render_retranslate_button(SUBTITLE_PROGRESS_HOST, key_suffix="after_video", disabled=_is_task_running()):
                return True
            selected_subtitle_mode, subtitle_ready = _render_generated_merge_choice()
            if st.button(t("Remerge video with selected subtitles"), key="remerge_generated_video", disabled=_is_task_running() or not subtitle_ready):
                suppress_upload_copy_autogenerate_once()
                with _task_guard("subtitle", reset_status=False):
                    process_subtitle_merge(SUBTITLE_PROGRESS_HOST, selected_subtitle_mode)
                st.rerun()
            if load_key("enable_upload_copy_suggestions"):
                render_upload_copy_suggestions(
                    _is_task_running,
                    auto_generate_missing=consume_upload_copy_autogenerate_setting(),
                )
            download_subtitle_zip_button(text=t("Download All Srt Files"))
            
            if st.button(t("Archive to 'history'"), key="cleanup_in_text_processing"):
                st.session_state["last_text_archive_dir"] = cleanup()
                st.rerun()
            return True

def process_text(progress_host=None, start_step=1):
    def transcribe_step():
        _2_asr.transcribe()

    def split_step():
        _3_1_split_nlp.split_by_spacy()
        _3_2_split_meaning.split_sentences_by_meaning()

    def translate_step():
        from core.translate_lines import assert_local_translator_ready
        assert_local_translator_ready()
        _4_1_summarize.get_summary()
        if load_key("pause_before_translate"):
            input(t("⚠️ PAUSE_BEFORE_TRANSLATE. Go to `output/log/terminology.json` to edit terminology. Then press ENTER to continue..."))
        _4_2_translate.translate_all()

    def split_subtitle_step():
        _5_split_sub.split_for_sub_main()

    def align_step():
        _6_gen_sub.align_timestamp_main()

    def merge_step():
        return _7_sub_into_vid.merge_subtitles_to_video()

    subtitle_steps = [
        (1, SUBTITLE_PROCESSING_STEPS[0], transcribe_step),
        (2, SUBTITLE_PROCESSING_STEPS[1], split_step),
        (3, SUBTITLE_PROCESSING_STEPS[2], translate_step),
        (4, SUBTITLE_PROCESSING_STEPS[3], split_subtitle_step),
        (5, SUBTITLE_PROCESSING_STEPS[4], align_step),
    ]
    start_step = max(1, min(int(start_step or 1), 6))
    for step_index, step_label, callback in subtitle_steps:
        if step_index >= start_step:
            _run_subtitle_step(step_index, progress_host, step_label, callback)
    if not load_key("burn_subtitles"):
        return
    if not _ambiguity_review_confirmed():
        status = _read_task_status()
        _write_task_status(
            "subtitle",
            status="awaiting_review",
            step_index=5,
            step_label=SUBTITLE_PROCESSING_STEPS[4],
            step_times=status.get("step_times", {}),
        )
        _render_subtitle_progress(progress_host, 5)
        return
    merged_video = _run_subtitle_step(6, progress_host, SUBTITLE_PROCESSING_STEPS[5], merge_step)
    if merged_video:
        st.session_state["last_text_merged_video"] = merged_video
    
    st.success(t("Subtitle processing complete! 🎉"))
    st.balloons()

def process_subtitle_merge(progress_host=None, subtitle_mode="bilingual_trans_top"):
    def merge_step():
        video_file, src_srt, trans_srt, _, _ = _prepare_generated_subtitle_inputs(subtitle_mode, sync=True)
        return _7_sub_into_vid.merge_subtitles_to_video(
            video_file=video_file,
            src_srt=src_srt,
            trans_srt=trans_srt,
            subtitle_mode=subtitle_mode,
        )

    merged_video = _run_subtitle_step(6, progress_host, SUBTITLE_PROCESSING_STEPS[5], merge_step)
    if merged_video:
        st.session_state["last_text_merged_video"] = merged_video
    st.success(t("Subtitle video merge complete! 🎉"))
    st.balloons()
    return merged_video

def maybe_auto_process_after_download():
    if not st.session_state.get("auto_process_after_download_pending"):
        return False
    if _find_sub_video():
        st.session_state["auto_process_after_download_pending"] = False
        return False
    if _is_task_running():
        st.info(t("A task is already running. Please wait until it finishes."))
        return False
    try:
        _1_ytdlp.find_video_files()
    except Exception:
        return False

    st.session_state["auto_process_after_download_pending"] = False
    with _task_guard("subtitle"):
        with st.spinner(t("Auto processing subtitles after download...")):
            process_text(SUBTITLE_PROGRESS_HOST)
    st.rerun()
    return True

def audio_processing_section():
    st.header(t("d. Dubbing"))
    with st.container(border=True):
        st.markdown(f"""
        <p style='font-size: 20px;'>
        {t("This stage includes the following steps:")}
        <p style='font-size: 20px;'>
            1. {t("Generate audio tasks and chunks")}<br>
            2. {t("Extract reference audio")}<br>
            3. {t("Generate and merge audio files")}<br>
            4. {t("Merge final audio into video")}
        """, unsafe_allow_html=True)
        _render_archived_dir_button("last_audio_archive_dir")
        if not os.path.exists(DUB_VIDEO):
            button_disabled = _is_task_running()
            if button_disabled:
                st.info(t("A task is already running. Please wait until it finishes."))
            if st.button(t("Start Audio Processing"), key="audio_processing_button", disabled=button_disabled):
                with _task_guard("audio"):
                    process_audio()
                st.rerun()
        else:
            st.success(t("Audio processing is complete! You can check the audio files in the `output` folder."))
            if load_key("burn_subtitles"):
                st.video(DUB_VIDEO) 
            if st.button(t("Delete dubbing files"), key="delete_dubbing_files"):
                delete_dubbing_files()
                st.rerun()
            if st.button(t("Archive to 'history'"), key="cleanup_in_audio_processing"):
                st.session_state["last_audio_archive_dir"] = cleanup()
                st.rerun()

def process_audio():
    with st.spinner(t("Generate audio tasks")): 
        _8_1_audio_task.gen_audio_task_main()
        _8_2_dub_chunks.gen_dub_chunks()
    with st.spinner(t("Extract refer audio")):
        _9_refer_audio.extract_refer_audio_main()
    with st.spinner(t("Generate all audio")):
        _10_gen_audio.gen_audio()
    with st.spinner(t("Merge full audio")):
        _11_merge_audio.merge_full_audio()
    with st.spinner(t("Merge dubbing to the video")):
        _12_dub_to_vid.merge_video_audio()
    
    st.success(t("Audio processing complete! 🎇"))
    st.balloons()

def main():
    logo_col, _ = st.columns([1,1])
    with logo_col:
        st.image("docs/logo.png", width="stretch")
    st.markdown(button_style, unsafe_allow_html=True)
    welcome_text = t("Hello, welcome to VideoLingo. If you encounter any issues, feel free to get instant answers with our Free QA Agent <a href=\"https://share.fastgpt.in/chat/share?shareId=066w11n3r9aq6879r4z0v9rh\" target=\"_blank\">here</a>! You can also try out our SaaS website at <a href=\"https://videolingo.io\" target=\"_blank\">videolingo.io</a> for free!")
    st.markdown(f"<p style='font-size: 20px; color: #808080;'>{welcome_text}</p>", unsafe_allow_html=True)
    # add settings
    with st.sidebar:
        page_setting()
        st.markdown(give_star_button, unsafe_allow_html=True)
    download_video_section()
    text_processing_section()
    manual_subtitle_merge_section()
    audio_processing_section()

if __name__ == "__main__":
    main()
