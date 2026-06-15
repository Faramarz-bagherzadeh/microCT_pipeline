import os
import re
import time
import subprocess
import streamlit as st
import json
from pathlib import Path

STAGE_NAME = "1-Denoising"


def save_stage_config(config):
    config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.json"))
    try:
        with open(config_file_path, "w") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        st.error(f"Failed to update config file: {e}")
        return False


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


def _write_slurm_for(template_path, target_path, input_value, output_value):
    with open(template_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Replace INPUT_DIR= and OUTPUT_DIR= lines (handles quotes or not)
    text = re.sub(r'INPUT_DIR\s*=.*', f'INPUT_DIR="{input_value}"', text)
    text = re.sub(r'OUTPUT_DIR\s*=.*', f'OUTPUT_DIR="{output_value}"', text)

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(text)


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


def _submit_and_wait(slurm_file, stop_flag_key="denoise_stop", poll_interval=5):
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
    st.write("Use this page to select raw input and denoising output directories.")

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
    denoising_output_dir = str(selected_output)

    # gather available .rek files
    raw_files = []
    if raw_directory_path and os.path.isdir(raw_directory_path):
        raw_files = [entry.name for entry in os.scandir(raw_directory_path) if entry.is_file() and entry.name.lower().endswith('.rek')]

    # show files with selection and processed columns
    if raw_files:
        st.markdown("---")
        st.write(f"Found {len(raw_files)} .rek files in the selected raw directory.")
        st.markdown("### Available raw files")

        # Initialize session states for all files first
        for file_name in sorted(raw_files):
            sel_key = f"rek_selected_{file_name}"
            done_key = f"rek_done_{file_name}"
            run_key = f"rek_running_{file_name}"
            failed_key = f"rek_failed_{file_name}"
            if sel_key not in st.session_state:
                st.session_state[sel_key] = False
            if done_key not in st.session_state:
                st.session_state[done_key] = False
            if run_key not in st.session_state:
                st.session_state[run_key] = False
            if failed_key not in st.session_state:
                st.session_state[failed_key] = False

        # Apply any pending unselect actions before widget creation
        pending_deselect = st.session_state.get("rek_deselect_pending", [])
        if pending_deselect:
            for sel_key in pending_deselect:
                st.session_state[sel_key] = False
            st.session_state["rek_deselect_pending"] = []

        # Define callback for Select All checkbox
        def update_select_all():
            select_all_state = st.session_state.get("rek_select_all", False)
            for file_name in raw_files:
                st.session_state[f"rek_selected_{file_name}"] = select_all_state

        # Select All checkbox
        select_all_key = "rek_select_all"
        if select_all_key not in st.session_state:
            st.session_state[select_all_key] = False

        st.checkbox("Select All", key=select_all_key, on_change=update_select_all)

        # Header row for status and file name
        header_status, header_file = st.columns([1, 5])
        header_status.markdown("**Status**")
        header_file.markdown("**File**")

        # Display individual file rows
        for file_name in sorted(raw_files):
            sel_key = f"rek_selected_{file_name}"
            done_key = f"rek_done_{file_name}"
            run_key = f"rek_running_{file_name}"
            failed_key = f"rek_failed_{file_name}"

            if st.session_state.get(failed_key, False):
                status = "Job Failed"
            elif st.session_state.get(done_key, False):
                status = "Completed"
            elif st.session_state.get(run_key, False):
                status = "Running"
            elif st.session_state.get(sel_key, False):
                status = "(Pending)"
            else:
                status = ""

            status_col, file_col = st.columns([1, 5])
            status_col.write(status)
            file_col.checkbox(file_name, key=sel_key)

    slurm_template = os.path.abspath(os.path.join(os.path.dirname(__file__), "slurm_denoising.slurm"))
    if not os.path.exists(slurm_template):
        st.error(f"SLURM template not found: {slurm_template}")
        return

    if "denoise_running" not in st.session_state:
        st.session_state.denoise_running = False
    if "denoise_stop" not in st.session_state:
        st.session_state.denoise_stop = False
    if "denoise_queue" not in st.session_state:
        st.session_state.denoise_queue = []
    if "denoise_queue_index" not in st.session_state:
        st.session_state.denoise_queue_index = 0
    if "denoise_phase" not in st.session_state:
        st.session_state.denoise_phase = ""

    col_submit, col_stop = st.columns(2)
    submit_pressed = col_submit.button("Submit jobs", use_container_width=True)
    stop_pressed = col_stop.button("Stop", use_container_width=True)

    if stop_pressed:
        st.session_state.denoise_stop = True

    if submit_pressed and not st.session_state.denoise_running:
        # collect selected files and initialize the queue
        to_run = [f for f in raw_files if st.session_state.get(f"rek_selected_{f}")]
        if not to_run:
            st.warning("No files selected. Please select files to submit.")
        else:
            st.session_state.denoise_running = True
            st.session_state.denoise_stop = False
            st.session_state.denoise_queue = to_run
            st.session_state.denoise_queue_index = 0
            st.session_state.denoise_phase = "start_job"
            st.session_state["rek_deselect_pending"] = []
            for fname in to_run:
                st.session_state[f"rek_failed_{fname}"] = False
            st.rerun()

    if st.session_state.denoise_running and st.session_state.denoise_queue:
        queue = st.session_state.denoise_queue
        idx = st.session_state.denoise_queue_index
        if idx < len(queue):
            fname = queue[idx]
            if st.session_state.denoise_phase == "start_job":
                st.session_state[f"rek_running_{fname}"] = True
                st.session_state.denoise_phase = "run_job"
                st.rerun()
            elif st.session_state.denoise_phase == "run_job":
                if st.session_state.denoise_stop:
                    st.info("Stopping further submissions.")
                    st.session_state.denoise_running = False
                    st.session_state.denoise_phase = ""
                    st.session_state.denoise_queue = []
                    st.session_state.denoise_queue_index = 0
                else:
                    input_val = os.path.join(raw_directory_path, fname)
                    output_val = denoising_output_dir

                    tmp_slurm = slurm_template + f".tmp.{idx}.slurm"
                    try:
                        _write_slurm_for(slurm_template, tmp_slurm, input_val, output_val)
                    except Exception as e:
                        st.error(f"Failed to prepare slurm file for {fname}: {e}")
                        st.session_state[f"rek_running_{fname}"] = False
                        st.session_state.denoise_running = False
                        st.session_state.denoise_phase = ""
                        st.session_state.denoise_queue = []
                        st.session_state.denoise_queue_index = 0
                        st.rerun()

                    st.info(f"Submitting {fname}...")
                    jobid, job_state = _submit_and_wait(tmp_slurm)
                    st.session_state[f"rek_running_{fname}"] = False
                    if jobid is None:
                        st.error(f"Submission failed for {fname}.")
                        st.session_state[f"rek_failed_{fname}"] = True
                    else:
                        if job_state == "COMPLETED":
                            st.success(f"Job {jobid} finished for {fname}.")
                            st.session_state[f"rek_done_{fname}"] = True
                            pending_deselect = st.session_state.get("rek_deselect_pending", [])
                            pending_deselect.append(f"rek_selected_{fname}")
                            st.session_state["rek_deselect_pending"] = pending_deselect
                        elif job_state == "STOPPED":
                            st.warning(f"Job {jobid} stopped for {fname}.")
                        else:
                            st.error(f"Job {jobid} failed for {fname}. State: {job_state}")
                            st.session_state[f"rek_failed_{fname}"] = True

                    st.session_state.denoise_queue_index += 1
                    if st.session_state.denoise_queue_index < len(queue):
                        st.session_state.denoise_phase = "start_job"
                        st.rerun()
                    else:
                        st.session_state.denoise_running = False
                        st.session_state.denoise_phase = ""
                        st.session_state.denoise_queue = []
                        st.session_state.denoise_queue_index = 0
                        if st.session_state.get("rek_deselect_pending"):
                            st.rerun()
        else:
            st.session_state.denoise_running = False
            st.session_state.denoise_phase = ""
            st.session_state.denoise_queue = []
            st.session_state.denoise_queue_index = 0
