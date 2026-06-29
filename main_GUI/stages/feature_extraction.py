import os
import re
import time
import subprocess
import streamlit as st
from pathlib import Path

STAGE_NAME = "5-Feature Extraction"


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


def find_tif_files(directory):
    """Recursively find all .tif files in the given directory."""
    tif_files = []
    try:
        for root, dirs, files in os.walk(directory):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in sorted(files):
                if f.endswith(".tif"):
                    tif_files.append(os.path.abspath(os.path.join(root, f)))
    except Exception:
        pass
    return tif_files


def _write_slurm_for(template_path, target_path, output_value, resolution_value, tif_file_list_path, num_tifs):
    with open(template_path, "r", encoding="utf-8") as f:
        text = f.read()

    text = re.sub(r'OUTPUT_DIR\s*=.*', f'OUTPUT_DIR="{output_value}"', text)
    text = re.sub(r'Resolution\s*=.*', f'Resolution="{resolution_value}"', text)
    text = re.sub(r'%MAX_JOBS%', str(num_tifs - 1), text)
    text = re.sub(r'TIFF_LIST\s*="".*', f'TIFF_LIST="{tif_file_list_path}"', text)

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


def _submit_and_wait(slurm_file, stop_flag_key="fe_stop", poll_interval=5):
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
    st.write("Configure and submit a feature extraction SLURM job array (one job per .tif file).")

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
        "Input directory (TIFF_DIR with .tif files)",
        dirs,
        format_func=lambda x: str(x.relative_to(base_dir)),
    )
    selected_output = st.selectbox(
        "Output directory",
        dirs,
        index=0,
        format_func=lambda x: str(x.relative_to(base_dir)),
    )

    raw_directory_path = str(selected_raw)
    feature_output_dir = str(selected_output)

    resolution = st.text_input("Resolution (voxel size in meter, e.g. 120e-6):", value="0.045")

    slurm_template = os.path.abspath(os.path.join(os.path.dirname(__file__), "slurm_feature_extraction.slurm"))
    if not os.path.exists(slurm_template):
        st.error(f"SLURM template not found: {slurm_template}")
        return

    # Scan for .tif files in the selected input directory
    tif_files = find_tif_files(raw_directory_path)
    if not tif_files:
        st.warning(f"No .tif files found in {raw_directory_path}")
        return

    st.info(f"Found {len(tif_files)} .tif file(s) in {raw_directory_path}")
    with st.expander("Show .tif files to be processed"):
        for tif_path in tif_files:
            st.text(tif_path)

    if "fe_running" not in st.session_state:
        st.session_state.fe_running = False
    if "fe_stop" not in st.session_state:
        st.session_state.fe_stop = False

    col_submit, col_stop = st.columns(2)
    submit_pressed = col_submit.button("Submit job array", use_container_width=True)
    stop_pressed = col_stop.button("Stop", use_container_width=True)

    if stop_pressed:
        st.session_state.fe_stop = True

    if submit_pressed and not st.session_state.fe_running:
        st.session_state.fe_running = True
        st.session_state.fe_stop = False

        # Write the list of .tif file paths to a temporary file
        tif_list_path = os.path.join(os.path.dirname(slurm_template), f"tif_list_{int(time.time())}.txt")
        try:
            with open(tif_list_path, "w", encoding="utf-8") as f:
                for tif_path in tif_files:
                    f.write(tif_path + "\n")
            st.info(f"Written {len(tif_files)} file paths to {tif_list_path}")
        except Exception as e:
            st.error(f"Failed to write tif list file: {e}")
            st.session_state.fe_running = False
            return

        # Write the SLURM script with proper substitutions
        tmp_slurm = slurm_template + ".tmp.slurm"
        try:
            _write_slurm_for(slurm_template, tmp_slurm, feature_output_dir,
                             resolution, tif_list_path, len(tif_files))
        except Exception as e:
            st.error(f"Failed to prepare slurm file: {e}")
            st.session_state.fe_running = False
            # Clean up the tif list file on error
            try:
                os.remove(tif_list_path)
            except Exception:
                pass
            return

        st.info(f"Submitting feature extraction job array for {len(tif_files)} .tif files...")
        jobid, job_state = _submit_and_wait(tmp_slurm, stop_flag_key="fe_stop")
        st.session_state.fe_running = False

        if jobid is None:
            st.error("Submission failed.")
        else:
            if job_state == "COMPLETED":
                st.success(f"Job array {jobid} completed successfully.")
            elif job_state == "STOPPED":
                st.warning(f"Job array {jobid} was stopped.")
            else:
                st.error(f"Job array {jobid} finished with state: {job_state}")