import os
import re
import time
import subprocess
import streamlit as st
from pathlib import Path

STAGE_NAME = "2-Segmentation"


def get_dirs(path):
    try:
        base = Path(path)
        if not base.is_dir():
            return []

        def is_hidden_dir(path_obj):
            return any(part.startswith(".") for part in path_obj.relative_to(base).parts)

        return [p for p in base.rglob("*") if p.is_dir() and not is_hidden_dir(p)]
    except Exception:
        return []


def _get_slurm_job_state(jobid):
    try:
        completed = subprocess.run(
            ["sacct", "-j", jobid, "--format=State", "--noheader", "-P"],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return None
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            return None
        return lines[0].split("|")[0]
    except Exception:
        return None


def _submit_and_wait(slurm_file, stop_flag_key="seg_stop", poll_interval=5):
    try:
        completed = subprocess.run(["sbatch", slurm_file], capture_output=True, text=True)
    except Exception as e:
        st.error(f"Failed to run sbatch: {e}")
        return None, "SUBMIT_FAILED"

    out = completed.stdout + completed.stderr
    m = re.search(r"Submitted batch job (\d+)", out)
    if not m:
        st.error(f"Could not determine job id from sbatch output:\n{out}")
        return None, "SUBMIT_FAILED"
    jobid = m.group(1)

    while True:
        if st.session_state.get(stop_flag_key):
            try:
                subprocess.run(["scancel", jobid], capture_output=True, text=True)
            except Exception:
                pass
            return jobid, "STOPPED"

        try:
            q = subprocess.run(["squeue", "-j", jobid], capture_output=True, text=True)
            if q.returncode != 0 or (jobid not in q.stdout):
                state = _get_slurm_job_state(jobid)
                return jobid, state or "UNKNOWN"
        except Exception:
            state = _get_slurm_job_state(jobid)
            return jobid, state or "UNKNOWN"

        time.sleep(poll_interval)


def render(config):
    st.subheader(STAGE_NAME)
    st.write("Use this page to select segmentation input and output directories.")

    base_dir = config.get("dir_picker_base", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    base_dir = st.text_input("Folder search base path:", value=base_dir)

    if not base_dir:
        st.warning("Enter a base path to search for folders.")
        return

    if not os.path.isdir(base_dir):
        st.error("Base path is not a valid directory.")
        return

    dirs = [Path(base_dir)] + get_dirs(base_dir)
    dirs = sorted(set(dirs), key=lambda p: str(p))
    if not dirs:
        st.warning("No directories found under the selected base path.")
        return

    selected_raw = st.selectbox(
        "Select raw files folder",
        dirs,
        format_func=lambda x: str(x.relative_to(base_dir)),
    )
    selected_output = st.selectbox(
        "Select output folder",
        dirs,
        index=0,
        format_func=lambda x: str(x.relative_to(base_dir)),
    )

    raw_directory_path = str(selected_raw)
    segmentation_output_dir = str(selected_output)

    raw_files = []
    if raw_directory_path and os.path.isdir(raw_directory_path):
        raw_files = [entry.name for entry in os.scandir(raw_directory_path) if entry.is_file() and entry.name.lower().endswith('.tif')]

    if raw_files:
        st.markdown("---")
        st.write(f"Found {len(raw_files)} .tif files in the selected raw directory.")
        st.markdown("### Available raw files")

        for file_name in sorted(raw_files):
            sel_key = f"seg_selected_{file_name}"
            if sel_key not in st.session_state:
                st.session_state[sel_key] = False

        def update_select_all():
            select_all_state = st.session_state.get("seg_select_all", False)
            for file_name in raw_files:
                st.session_state[f"seg_selected_{file_name}"] = select_all_state

        select_all_key = "seg_select_all"
        if select_all_key not in st.session_state:
            st.session_state[select_all_key] = False

        st.checkbox("Select All", key=select_all_key, on_change=update_select_all)

        for file_name in sorted(raw_files):
            sel_key = f"seg_selected_{file_name}"
            st.checkbox(file_name, key=sel_key)

    slurm_template = os.path.abspath(os.path.join(os.path.dirname(__file__), "slurm_segmentation.slurm"))
    if not os.path.exists(slurm_template):
        st.error(f"SLURM template not found: {slurm_template}")
        return

    if "segmentation_running" not in st.session_state:
        st.session_state.segmentation_running = False
    if "seg_stop" not in st.session_state:
        st.session_state.seg_stop = False

    col_submit, col_stop = st.columns(2)
    submit_pressed = col_submit.button("Submit jobs", use_container_width=True)
    stop_pressed = col_stop.button("Stop", use_container_width=True)

    if stop_pressed:
        st.session_state.seg_stop = True

    if submit_pressed and not st.session_state.segmentation_running:
        to_run = [f for f in raw_files if st.session_state.get(f"seg_selected_{f}")]
        if not to_run:
            st.warning("No files selected. Please select files to submit.")
        else:
            st.session_state.segmentation_running = True
            st.session_state.seg_stop = False

            # Full paths of selected files
            files = [os.path.join(raw_directory_path, f) for f in sorted(to_run)]

            try:
                with open(slurm_template, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception as e:
                st.error(f"Failed to read slurm template: {e}")
                st.session_state.segmentation_running = False
                return

            # Build FILES array with quoted paths
            file_entries = " ".join(f'"{path}"' for path in files)
            text = re.sub(r'FILES=\s*\(.*\)', f'FILES=( {file_entries} )', text)
            text = re.sub(r'OUTPUT_DIR\s*=.*', f'OUTPUT_DIR="{segmentation_output_dir}"', text)
            text = re.sub(r'%MAX_JOBS%', str(len(files) - 1), text)

            tmp_slurm = slurm_template + ".array.tmp.slurm"
            try:
                with open(tmp_slurm, "w", encoding="utf-8") as f:
                    f.write(text)
            except Exception as e:
                st.error(f"Failed to write slurm file: {e}")
                st.session_state.segmentation_running = False
                return

            st.info(f"Submitting segmentation job array for {len(files)} files (max 50 concurrent)...")
            jobid, job_state = _submit_and_wait(tmp_slurm)
            st.session_state.segmentation_running = False

            if jobid is None:
                st.error("Submission failed.")
            else:
                if job_state == "COMPLETED":
                    st.success(f"Job array {jobid} completed successfully.")
                elif job_state == "STOPPED":
                    st.warning(f"Job array {jobid} was stopped.")
                else:
                    st.error(f"Job array {jobid} finished with state: {job_state}")