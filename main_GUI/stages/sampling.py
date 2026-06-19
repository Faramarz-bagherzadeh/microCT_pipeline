import os
import re
import subprocess
import time
import streamlit as st
import json
from pathlib import Path

STAGE_NAME = "4-Sampling"


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


def dirs_containing_excel(dirs):
    """Return only directories that contain at least one .xlsx or .xls file."""
    result = []
    for d in dirs:
        try:
            has_excel = any(
                entry.name.lower().endswith((".xlsx", ".xls"))
                for entry in os.scandir(str(d))
                if entry.is_file()
            )
            if has_excel:
                result.append(d)
        except Exception:
            continue
    return result


def get_excel_files(directory):
    """Return a sorted list of Excel files (.xlsx, .xls) in the given directory."""
    files = []
    if directory and os.path.isdir(directory):
        for entry in os.scandir(directory):
            if entry.is_file() and entry.name.lower().endswith((".xlsx", ".xls")):
                files.append(entry.name)
    return sorted(files)


FINISHED_STATES = {"COMPLETED", "FAILED", "TIMEOUT", "CANCELLED", "NODE_FAIL", "PREEMPTED", "OUT_OF_MEMORY"}


def check_job_status(job_id):
    """Check SLURM job status using sacct.  Returns the state string or 'UNKNOWN'."""
    try:
        result = subprocess.run(
            ["sacct", "-j", str(job_id), "--format", "State", "--noheader", "-X"],
            capture_output=True, text=True, timeout=10,
        )
        state = result.stdout.strip().splitlines()
        return state[0].strip() if state else "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def render(config):
    st.subheader(STAGE_NAME)
    st.write("Select the input directories, the weights Excel file, the output directory, and set sampling parameters.")

    base_dir = config.get("dir_picker_base", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    base_dir = st.text_input("Folder search base path:", value=base_dir)

    if not base_dir:
        st.warning("Enter a base path to search for folders.")
        return

    if not os.path.isdir(base_dir):
        st.error("Base path is not a valid directory.")
        return

    all_dirs = [Path(base_dir)] + get_dirs(base_dir)
    all_dirs = sorted(set(all_dirs), key=lambda p: str(p))

    if not all_dirs:
        st.warning("No directories found under the selected base path.")
        return

    # Filter to directories containing Excel files (for weights directory)
    excel_dirs = dirs_containing_excel(all_dirs)

    if not excel_dirs:
        st.warning("No directories with Excel files (.xlsx/.xls) found under the selected base path.")
        return

    st.markdown("### Input Directories")

    # Directory 1: TIF files (all directories)
    selected_tiff_dir = st.selectbox(
        "Select input directory containing .tif files",
        all_dirs,
        index=0,
        format_func=lambda x: str(x.relative_to(base_dir)),
        key="tiff_dir_select",
    )

    # Directory 2: Directory containing the weights Excel file
    selected_weights_dir = st.selectbox(
        "Select directory containing the weights Excel file",
        excel_dirs,
        format_func=lambda x: str(x.relative_to(base_dir)),
        key="weights_dir_select",
    )

    # Show Excel files in the selected weights directory and let user pick one
    weights_dir_path = str(selected_weights_dir)
    excel_files = get_excel_files(weights_dir_path)

    if excel_files:
        selected_excel = st.selectbox(
            "Select the weights Excel file",
            excel_files,
            key="weights_file_select",
        )
        weights_file_full_path = os.path.join(weights_dir_path, selected_excel)
    else:
        st.warning("No Excel files found in the selected directory.")
        st.stop()
        return

    st.markdown("### Output Directory")
    selected_output = st.selectbox(
        "Select output directory (for sampling results)",
        all_dirs,
        index=0,
        format_func=lambda x: str(x.relative_to(base_dir)),
        key="output_dir_select",
    )

    tiff_directory_path = str(selected_tiff_dir)
    output_directory_path = str(selected_output)

    st.markdown("### Sampling Parameters")
    sample_size = st.number_input("Sample size (number of layers)", min_value=1, value=100, step=1, key="sample_size_input")
    overlap_size = st.number_input("Overlap size (number of layers)", min_value=0, value=10, step=1, key="overlap_size_input")

    # Reference to the slurm template
    slurm_template = os.path.abspath(os.path.join(os.path.dirname(__file__), "slurm_sampling.slurm"))
    if not os.path.exists(slurm_template):
        st.error(f"SLURM template not found: {slurm_template}")
        return

    col_run, col_stop = st.columns(2)
    run_pressed = col_run.button("Run Sampling", width='stretch')
    stop_pressed = col_stop.button("Stop", width='stretch')

    if run_pressed:
        # Write the slurm script with TIFF_DIR, WEIGHTS_FILE, OUTPUT_DIR, SAMPLE_SIZE and OVERLAP_SIZE set
        try:
            with open(slurm_template, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            st.error(f"Failed to read slurm template: {e}")
            return

        text = re.sub(r'TIFF_DIR\s*=.*', f'TIFF_DIR="{tiff_directory_path}"', text)
        text = re.sub(r'WEIGHTS_FILE\s*=.*', f'WEIGHTS_FILE="{weights_file_full_path}"', text)
        text = re.sub(r'OUTPUT_DIR\s*=.*', f'OUTPUT_DIR="{output_directory_path}"', text)
        text = re.sub(r'SAMPLE_SIZE\s*=.*', f'SAMPLE_SIZE="{sample_size}"', text)
        text = re.sub(r'OVERLAP_SIZE\s*=.*', f'OVERLAP_SIZE="{overlap_size}"', text)

        temp_slurm = slurm_template + ".tmp.slurm"
        try:
            with open(temp_slurm, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            st.error(f"Failed to write temporary slurm file: {e}")
            return

        # Submit the job
        try:
            completed = subprocess.run(["sbatch", temp_slurm], capture_output=True, text=True)
        except Exception as e:
            st.error(f"Failed to run sbatch: {e}")
            return

        out = completed.stdout + completed.stderr
        m = re.search(r"Submitted batch job (\d+)", out)
        if m:
            jobid = m.group(1)
            st.success(f"Sampling job submitted (Job ID: {jobid})")
            st.session_state["sampling_job_id"] = jobid
            st.session_state["sampling_submit_time"] = time.time()
            st.session_state["sampling_output_dir"] = output_directory_path
            # Clear any stale completion state
            st.session_state.pop("sampling_job_completed_time", None)
            st.session_state.pop("sampling_job_finished", None)
            st.rerun()
        else:
            st.error(f"Could not determine job id from sbatch output:\n{out}")

    # ===== Post-submission flow =====
    # Check if we have an active job to monitor
    if "sampling_job_id" in st.session_state:
        job_id = st.session_state["sampling_job_id"]
        output_dir = st.session_state.get("sampling_output_dir", "")

        # --- Phase 1: Waiting for the SLURM job to finish ---
        if "sampling_job_completed_time" not in st.session_state:
            status = check_job_status(job_id)
            st.info(f"Job {job_id} is running. Current status: {status}")

            if status in FINISHED_STATES:
                # Job just finished – record the completion time
                st.session_state["sampling_job_completed_time"] = time.time()
                st.rerun()
            else:
                st.write("Waiting for the SLURM job to finish. Check again shortly.")
                if st.button("Check Job Status", width='stretch'):
                    st.rerun()

        # --- Phase 2: Job finished, show completion message ---
        elif "sampling_job_finished" not in st.session_state:
            st.session_state["sampling_job_finished"] = True
            st.success(f"Sampling job {job_id} has completed. Results are in: {output_dir}")
            st.rerun()

        # --- Phase 3: Display completion info ---
        if st.session_state.get("sampling_job_finished", False):
            st.success(f"Sampling job {job_id} completed successfully.")
            st.write(f"Output directory: **{output_dir}**")

            # Allow the user to dismiss / reset
            if st.button("Clear & Submit New Job", width='stretch'):
                for key in ["sampling_job_id", "sampling_submit_time",
                            "sampling_output_dir", "sampling_job_completed_time",
                            "sampling_job_finished"]:
                    st.session_state.pop(key, None)
                st.rerun()