import streamlit as st
import os
import subprocess
import json

st.title("Micro CT pipe line")

# Initialize session state for master sheet verification and data directory count
if "master_sheet_verified" not in st.session_state:
    st.session_state.master_sheet_verified = False
if "data_dir_count" not in st.session_state:
    st.session_state.data_dir_count = None
if "master_sheet_abs_path" not in st.session_state:
    st.session_state.master_sheet_abs_path = None
if "data_dir_abs_path" not in st.session_state:
    st.session_state.data_dir_abs_path = None

# Path verification section
st.subheader("Path Configuration")
col1, col2 = st.columns(2)

with col1:
    master_sheet_path = st.text_input("Master sheet file path:", placeholder="Enter the path to your master sheet file")

with col2:
    data_dir_path = st.text_input("Data directory path:", placeholder="Enter the path to your data directory")

# Single verify button
if st.button("Verify Paths", use_container_width=True):
    if not master_sheet_path or not data_dir_path:
        st.error("✗ Please enter both paths")
        st.session_state.master_sheet_verified = False
        st.session_state.data_dir_count = None
    elif not os.path.exists(master_sheet_path):
        st.error("✗ Master sheet file not found")
        st.session_state.master_sheet_verified = False
        st.session_state.data_dir_count = None
    elif not os.path.isdir(data_dir_path):
        st.error("✗ Data directory not found")
        st.session_state.master_sheet_verified = False
        st.session_state.data_dir_count = None
    else:
        # Both paths exist - count files and save
        file_count = sum(
            1 for entry in os.scandir(data_dir_path) if entry.is_file()
        )
        st.session_state.master_sheet_verified = True
        st.session_state.data_dir_count = file_count
        st.session_state.master_sheet_abs_path = os.path.abspath(master_sheet_path)
        st.session_state.data_dir_abs_path = os.path.abspath(data_dir_path)
        
        # Save to JSON
        config_data = {
            "master_sheet_path": st.session_state.master_sheet_abs_path,
            "data_directory_path": st.session_state.data_dir_abs_path,
            "file_count": st.session_state.data_dir_count
        }
        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=4)
        
        st.success(f"✓ Paths verified and saved to config.json")
        st.info(f"Master sheet: {st.session_state.master_sheet_abs_path}")
        st.info(f"Data directory: {st.session_state.data_dir_abs_path} ({file_count} files)")

st.divider()

# Job submission section
st.subheader("SLURM Job Submission")

if not st.session_state.master_sheet_verified or st.session_state.data_dir_count is None:
    st.warning("⚠️ Please verify both paths first to launch jobs")

job = st.selectbox("Select pipeline stage", [
    "1-Denoising",
    "2-Segmentation",
    "3-Weight Checking",
    "4-Sampling",
    "5-Feature Extraction",
    "6-Merging data",
])

submit_button = st.button("Submit SLURM job", disabled=not (st.session_state.master_sheet_verified and st.session_state.data_dir_count is not None))

if submit_button:
    slurm_script = f"slurm/{job}.slurm"

    cmd = ["sbatch", slurm_script]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        st.text(completed.stdout)
        st.text(completed.stderr)
        if completed.returncode != 0:
            st.error(f"sbatch exited with return code {completed.returncode}")
    except Exception as exc:
        st.error(f"Failed to submit SLURM job: {exc}")
