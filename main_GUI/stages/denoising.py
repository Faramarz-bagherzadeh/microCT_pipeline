import os
import subprocess
import streamlit as st
import pandas as pd
import json

STAGE_NAME = "1-Denoising"

EXPECTED_COLUMNS = ["file_name", "start_depth", "end_depth"]


def load_master_sheet(path):
    try:
        if path.lower().endswith(".csv"):
            return pd.read_csv(path)
        else:
            return pd.read_excel(path)
    except Exception as e:
        st.error(f"Failed to read master sheet: {e}")
        return None


def save_stage_config(config, denoising_output_dir):
    config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.json"))
    config_copy = config.copy()
    config_copy["denoising_output_dir"] = denoising_output_dir
    try:
        with open(config_file_path, "w") as f:
            json.dump(config_copy, f, indent=4)
        return True
    except Exception as e:
        st.error(f"Failed to update config file: {e}")
        return False


def render(config):
    st.subheader(STAGE_NAME)
    st.write("Use this page to design the denoising stage inputs and parameters.")
    st.write(f"Master sheet: {config['master_sheet_path']}")
    st.write(f"Data directory: {config['data_directory_path']}")
    st.write(f"File count: {config['file_count']}")

    df = load_master_sheet(config["master_sheet_path"])
    if df is None:
        return

    if df.empty:
        st.warning("Master sheet is empty.")
        return

    # Normalize columns if possible
    lower_columns = {col.lower(): col for col in df.columns}
    if "file_name" not in lower_columns:
        if "name" in lower_columns:
            lower_columns["file_name"] = lower_columns["name"]
        elif "raw_file" in lower_columns:
            lower_columns["file_name"] = lower_columns["raw_file"]

    if "start_depth" not in lower_columns or "end_depth" not in lower_columns or "file_name" not in lower_columns:
        st.warning(f"Master sheet should contain columns for file name, start depth, and end depth. Found: {', '.join(df.columns)}")
        return

    rows = []
    for _, row in df.iterrows():
        rows.append({
            "file_name": row[lower_columns["file_name"]],
            "start_depth": row[lower_columns["start_depth"]],
            "end_depth": row[lower_columns["end_depth"]],
        })

    st.markdown("### Raw files to denoise")
    for idx, row in enumerate(rows):
        raw_name = str(row["file_name"])
        processed_key = f"denoise_processed_{idx}_{raw_name}"
        if processed_key not in st.session_state:
            st.session_state[processed_key] = False

        col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
        col1.write(raw_name)
        col2.write(str(row["start_depth"]))
        col3.write(str(row["end_depth"]))
        col4.checkbox("Done", value=st.session_state[processed_key], disabled=True, key=processed_key)

    st.markdown("---")
    output_dir = st.text_input("Denoising output directory:", placeholder="Enter the path to the denoised output directory")
    output_dir_abs = None
    if output_dir:
        output_dir_abs = os.path.abspath(output_dir)
        st.write(f"Absolute output directory: {output_dir_abs}")
        if not os.path.isdir(output_dir_abs):
            st.warning("The output directory does not exist yet. Create it first or enter an existing directory.")

    slurm_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "slurm", "1-Denoising.slurm"))
    if not os.path.exists(slurm_script):
        st.error(f"SLURM script not found: {slurm_script}")
        return

    if st.button("Submit jobs", use_container_width=True):
        if not output_dir:
            st.error("✗ Please enter the denoising output directory.")
            return
        if not os.path.isdir(output_dir_abs):
            st.error("✗ Output directory not found. Please use an existing directory.")
            return

        if save_stage_config(config, output_dir_abs):
            st.success("✓ Denoising output directory saved to config.json")

        cmd = ["sbatch", slurm_script]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
            st.text(completed.stdout)
            st.text(completed.stderr)
            if completed.returncode == 0:
                st.success("SLURM job submitted successfully.")
                for idx, row in enumerate(rows):
                    raw_name = str(row["file_name"])
                    processed_key = f"denoise_processed_{idx}_{raw_name}"
                    st.session_state[processed_key] = True
            else:
                st.error(f"sbatch exited with return code {completed.returncode}")
        except Exception as exc:
            st.error(f"Failed to submit SLURM job: {exc}")

    if any(st.session_state.get(f"denoise_processed_{idx}_{str(row['file_name'])}", False) for idx, row in enumerate(rows)):
        st.info("Some files are marked done in the denoising stage.")
