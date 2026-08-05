import os
import re
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

        # Initialize selection state for all files
        for file_name in sorted(raw_files):
            sel_key = f"rek_selected_{file_name}"
            if sel_key not in st.session_state:
                st.session_state[sel_key] = False

        # Define callback for Select All checkbox
        def update_select_all():
            select_all_state = st.session_state.get("rek_select_all", False)
            for file_name in raw_files:
                st.session_state[f"rek_selected_{file_name}"] = select_all_state

        select_all_key = "rek_select_all"
        if select_all_key not in st.session_state:
            st.session_state[select_all_key] = False

        st.checkbox("Select All", key=select_all_key, on_change=update_select_all)

        # Display file checkboxes (no status column)
        for file_name in sorted(raw_files):
            sel_key = f"rek_selected_{file_name}"
            st.checkbox(file_name, key=sel_key)

    slurm_template = os.path.abspath(os.path.join(os.path.dirname(__file__), "slurm_denoising.slurm"))
    if not os.path.exists(slurm_template):
        st.error(f"SLURM template not found: {slurm_template}")
        return

    col_submit, col_stop = st.columns(2)
    submit_pressed = col_submit.button("Submit jobs", use_container_width=True)
    stop_pressed = col_stop.button("Stop", use_container_width=True)

    if stop_pressed:
        jobid = st.session_state.get("denoising_job_id")
        if not jobid:
            st.warning("No denoising job has been submitted yet.")
        else:
            try:
                completed = subprocess.run(["scancel", str(jobid)], capture_output=True, text=True)
            except Exception as e:
                st.error(f"Failed to run scancel: {e}")
            else:
                out = completed.stdout + completed.stderr
                if completed.returncode == 0:
                    st.success(f"Cancelled job {jobid}")
                    st.session_state.pop("denoising_job_id", None)
                else:
                    st.error(f"Failed to cancel job {jobid}:\n{out}")

    if submit_pressed:
        # collect selected files
        to_run = [f for f in raw_files if st.session_state.get(f"rek_selected_{f}")]
        if not to_run:
            st.warning("No files selected. Please select files to submit.")
        else:
            # full file paths of selected .rek files
            files = [os.path.join(raw_directory_path, f) for f in sorted(to_run)]
            # build a script that contains FILES array and uses SLURM_ARRAY_TASK_ID
            try:
                with open(slurm_template, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception as e:
                st.error(f"Failed to read slurm template: {e}")
                return

            # create bash array of file paths (quoted)
            file_entries = " ".join(f'"{path}"' for path in files)
            files_array_snippet = f"FILES=( {file_entries} )\nINPUT_DIR=\"${{FILES[$SLURM_ARRAY_TASK_ID]}}\""

            # replace INPUT_DIR and OUTPUT_DIR in template
            text = re.sub(r'INPUT_DIR\s*=.*', files_array_snippet, text)
            text = re.sub(r'OUTPUT_DIR\s*=.*', f'OUTPUT_DIR="{denoising_output_dir}"', text)

            array_slurm = slurm_template + ".array.tmp.slurm"
            try:
                with open(array_slurm, "w", encoding="utf-8") as f:
                    f.write(text)
            except Exception as e:
                st.error(f"Failed to write array slurm file: {e}")
                return

            # submit as array with concurrency limit 3
            array_spec = f"0-{len(files)-1}%3" if len(files) > 1 else "0-0%3"
            try:
                completed = subprocess.run(["sbatch", f"--array={array_spec}", array_slurm], capture_output=True, text=True)
            except Exception as e:
                st.error(f"Failed to run sbatch for array job: {e}")
                return

            out = completed.stdout + completed.stderr
            m = re.search(r"Submitted batch job (\d+)", out)
            if m:
                jobid = m.group(1)
                st.session_state["denoising_job_id"] = jobid
                st.success(f"Submitted array job {jobid} for {len(files)} files (concurrency capped at 3)")
            else:
                st.error(f"Could not determine job id from sbatch output:\n{out}")
