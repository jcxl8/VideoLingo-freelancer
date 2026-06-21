import os
import re
import shutil
import subprocess
from time import sleep

import streamlit as st
from core._1_ytdlp import download_video_ytdlp, find_video_files
from core.st_utils.task_runner import TaskRunner
from core.utils import *
from translations.translations import translate as t

OUTPUT_DIR = "output"
VIDEO_DESCRIPTION_FILE = os.path.join(OUTPUT_DIR, "video_description.md")
DOWNLOAD_RUNNER = TaskRunner()

def _read_video_description():
    if not os.path.exists(VIDEO_DESCRIPTION_FILE):
        return ""
    with open(VIDEO_DESCRIPTION_FILE, "r", encoding="utf-8") as f:
        return f.read()

def _save_video_description(description):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(VIDEO_DESCRIPTION_FILE, "w", encoding="utf-8") as f:
        f.write(description or "")

def _render_video_description_editor():
    current_description = _read_video_description()
    edited_description = st.text_area(
        t("Video Description"),
        value=current_description,
        height=180,
        key="video_description_editor",
        help=t("This description is saved with the video and archived to history.")
    )
    if edited_description != current_description:
        _save_video_description(edited_description)

def _download_guard():
    if DOWNLOAD_RUNNER.is_running():
        raise RuntimeError(t("A task is already running. Please wait until it finishes."))
    return DOWNLOAD_RUNNER.guard("download", clear_status_on_success=True)

def download_video_section():
    st.header(t("a. Download or Upload Video"))
    with st.container(border=True):
        video_file = find_video_files()
        if video_file is not None:
            st.video(video_file)
            _render_video_description_editor()
            if st.button(t("Delete and Reselect"), key="delete_video_button"):
                os.remove(video_file)
                if os.path.exists(OUTPUT_DIR):
                    shutil.rmtree(OUTPUT_DIR)
                sleep(1)
                st.rerun()
            return True
        else:
            # No existing video found — show download/upload UI
            col1, col2 = st.columns([3, 1])
            with col1:
                url = st.text_input(t("Enter YouTube link:"))
            with col2:
                res_dict = {
                    "360p": "360",
                    "1080p": "1080",
                    "Best": "best"
                }
                target_res = load_key("ytb_resolution")
                res_options = list(res_dict.keys())
                default_idx = list(res_dict.values()).index(target_res) if target_res in res_dict.values() else 0
                res_display = st.selectbox(t("Resolution"), options=res_options, index=default_idx)
                res = res_dict[res_display]
            auto_process = st.checkbox(t("Auto start subtitle processing after download"), key="auto_process_after_download")
            task_running = DOWNLOAD_RUNNER.is_running()
            if task_running:
                st.info(t("A task is already running. Please wait until it finishes."))
            if st.button(t("Download Video"), key="download_button", width="stretch", disabled=task_running):
                if url:
                    with st.spinner("Downloading video..."):
                        try:
                            with _download_guard():
                                download_video_ytdlp(url, resolution=res)
                        except Exception as e:
                            st.error(str(e))
                            return False
                    if auto_process:
                        st.session_state["auto_process_after_download_pending"] = True
                    st.rerun()

            uploaded_file = st.file_uploader(
                t("Or upload video"),
                type=load_key("allowed_video_formats") + load_key("allowed_audio_formats"),
                disabled=task_running,
            )
            if uploaded_file:
                if os.path.exists(OUTPUT_DIR):
                    shutil.rmtree(OUTPUT_DIR)
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                
                raw_name = uploaded_file.name.replace(' ', '_')
                name, ext = os.path.splitext(raw_name)
                clean_name = re.sub(r'[^\w\-_\.]', '', name) + ext.lower()
                    
                with open(os.path.join(OUTPUT_DIR, clean_name), "wb") as f:
                    f.write(uploaded_file.getbuffer())

                if ext.lower() in load_key("allowed_audio_formats"):
                    convert_audio_to_video(os.path.join(OUTPUT_DIR, clean_name))
                if not os.path.exists(VIDEO_DESCRIPTION_FILE):
                    _save_video_description("")
                st.rerun()
            else:
                return False

def convert_audio_to_video(audio_file: str) -> str:
    output_video = os.path.join(OUTPUT_DIR, 'black_screen.mp4')
    if not os.path.exists(output_video):
        print(f"🎵➡️🎬 Converting audio to video with FFmpeg ......")
        ffmpeg_cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=640x360', '-i', audio_file, '-shortest', '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p', output_video]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True, encoding='utf-8')
        print(f"🎵➡️🎬 Converted <{audio_file}> to <{output_video}> with FFmpeg\n")
        # delete audio file
        os.remove(audio_file)
    return output_video
