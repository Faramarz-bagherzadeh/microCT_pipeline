import os
import re
import time
import subprocess
import streamlit as st
from pathlib import Path

STAGE_NAME = "6-Merging data"


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


def find_json_files(directory):
    """Recursively find all .json files in the given directory."""
    json_files = []
    try:
        for root, dirs, files in os.walk(directory):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in sorted(files):
                if f.endswith(".json"):
                    json_files.append(os.path.abspath(os.path.join(root, f)))
    except Exception:
        pass
    return json_files


def _write_slurm_for(template_path, target_path, jsons_dir_value):
    with open(template_path, "r", encoding="utf-8") as f:
        text = f.read()

    text = re.sub(r'JSONS_DIR\s*=.*', f'JSONS_DIR="{jsons_dir_value}"', text)

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


def _submit_and_wait(slurm_file, stop_flag_key="merging_stop", poll_interval=5):
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
    st.write("Select a directory containing JSON feature files, then submit a SLURM job to merge them into a single Excel file.")

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

    selected_dir = st.selectbox(
        "Select a directory containing JSON files to merge",
        dirs,
        format_func=lambda x: str(x.relative_to(base_dir)),
    )

    jsons_dir = str(selected_dir)

    # Scan for JSON files in the selected directory
    json_files = find_json_files(jsons_dir)
    if not json_files:
        st.warning(f"No .json files found in {jsons_dir}")
        return

    st.info(f"Found {len(json_files)} .json file(s) in {jsons_dir}")
    with st.expander("Show JSON files to be merged"):
        for json_path in json_files:
            st.text(json_path)

    slurm_template = os.path.abspath(os.path.join(os.path.dirname(__file__), "slurm_merging_json.slurm"))
    if not os.path.exists(slurm_template):
        st.error(f"SLURM template not found: {slurm_template}")
        return

    if "merging_running" not in st.session_state:
        st.session_state.merging_running = False
    if "merging_stop" not in st.session_state:
        st.session_state.merging_stop = False

    col_submit, col_stop = st.columns(2)
    submit_pressed = col_submit.button("Submit merging job", use_container_width=True)
    stop_pressed = col_stop.button("Stop", use_container_width=True)

    if stop_pressed:
        st.session_state.merging_stop = True

    if submit_pressed and not st.session_state.merging_running:
        st.session_state.merging_running = True
        st.session_state.merging_stop = False

        # Write the SLURM script with proper substitutions
        tmp_slurm = slurm_template + ".tmp.slurm"
        try:
            _write_slurm_for(slurm_template, tmp_slurm, jsons_dir)
        except Exception as e:
            st.error(f"Failed to prepare slurm file: {e}")
            st.session_state.merging_running = False
            return

        st.info("Submitting merging job...")
        jobid, job_state = _submit_and_wait(tmp_slurm, stop_flag_key="merging_stop")
        st.session_state.merging_running = False

        if jobid is None:
            st.error("Submission failed.")
        else:
            if job_state == "COMPLETED":
                st.success(f"Job {jobid} completed successfully.")

                # Look for the output Excel file
                expected_excel = os.path.join(jsons_dir, "merged_features.xlsx")
                if os.path.exists(expected_excel):
                    with open(expected_excel, "rb") as f:
                        excel_bytes = f.read()
                    st.download_button(
                        label="Download merged Excel file",
                        data=excel_bytes,
                        file_name="merged_features.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                else:
                    st.warning(f"Expected output file not found: {expected_excel}")
            elif job_state == "STOPPED":
                st.warning(f"Job {jobid} was stopped.")
            else:
                st.error(f"Job {jobid} finished with state: {job_state}")