import os
import re
import subprocess
import time
import streamlit as st
import json
from pathlib import Path
from PIL import Image

STAGE_NAME = "3-Weight Checking"


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


def render(config):
    st.subheader(STAGE_NAME)
    st.write("Select the input directories, the weights Excel file, and the output directory for weight checking.")

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
        "Select output directory (for weight checking results)",
        all_dirs,
        index=0,
        format_func=lambda x: str(x.relative_to(base_dir)),
        key="output_dir_select",
    )

    tiff_directory_path = str(selected_tiff_dir)
    output_directory_path = str(selected_output)

    # Reference to the slurm template
    slurm_template = os.path.abspath(os.path.join(os.path.dirname(__file__), "slurm_weight_checking.slurm"))
    if not os.path.exists(slurm_template):
        st.error(f"SLURM template not found: {slurm_template}")
        return

    col_run, col_stop = st.columns(2)
    run_pressed = col_run.button("Run Weight Check", use_container_width=True)
    stop_pressed = col_stop.button("Stop", use_container_width=True)

    if run_pressed:
        # Write the slurm script with TIFF_DIR, WEIGHTS_FILE and OUTPUT_DIR set
        try:
            with open(slurm_template, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            st.error(f"Failed to read slurm template: {e}")
            return

        text = re.sub(r'TIFF_DIR\s*=.*', f'TIFF_DIR="{tiff_directory_path}"', text)
        text = re.sub(r'WEIGHTS_FILE\s*=.*', f'WEIGHTS_FILE="{weights_file_full_path}"', text)
        text = re.sub(r'OUTPUT_DIR\s*=.*', f'OUTPUT_DIR="{output_directory_path}"', text)

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
            st.success(f"Weight check job submitted (Job ID: {jobid})")
            st.session_state["weight_check_job_id"] = jobid
            st.session_state["weight_check_submit_time"] = time.time()
            st.session_state["weight_check_output_dir"] = output_directory_path
        else:
            st.error(f"Could not determine job id from sbatch output:\n{out}")

    # After submission, wait 2 minutes then show the "Show Figures" button
    if "weight_check_submit_time" in st.session_state:
        elapsed = time.time() - st.session_state["weight_check_submit_time"]
        remaining = 120 - elapsed

        if remaining > 0:
            st.info(f"Job submitted. Please wait {int(remaining)} more seconds before viewing figures...")
            if st.button("Check Now (skip wait)", use_container_width=True):
                remaining = 0

        if remaining <= 0:
            output_dir = st.session_state.get("weight_check_output_dir", "")
            fig1_path = os.path.join(output_dir, "fig1.png")
            fig2_path = os.path.join(output_dir, "fig2.png")

            if st.button("Show Figures", use_container_width=True):
                col1, col2 = st.columns(2)
                with col1:
                    if os.path.exists(fig1_path):
                        img1 = Image.open(fig1_path)
                        st.image(img1, caption="Fig 1", use_container_width=True)
                    else:
                        st.warning(f"fig1.png not found in {output_dir}")

                with col2:
                    if os.path.exists(fig2_path):
                        img2 = Image.open(fig2_path)
                        st.image(img2, caption="Fig 2", use_container_width=True)
                    else:
                        st.warning(f"fig2.png not found in {output_dir}")