import streamlit as st
import paramiko
import os

st.title("Micro CT pipe line")

# Initialize session state for master sheet verification and data directory count
if "master_sheet_verified" not in st.session_state:
    st.session_state.master_sheet_verified = False
if "data_dir_count" not in st.session_state:
    st.session_state.data_dir_count = None

# Master sheet existence check (moved to top)
st.subheader("Master Sheet Checker")
col1, col2 = st.columns([4, 1])

with col1:
    master_sheet_path = st.text_input("Master sheet file path:", placeholder="Enter the path to your master sheet file")

with col2:
    st.write("")  # Add spacing
    if st.button("Check"):
        if master_sheet_path:
            if os.path.exists(master_sheet_path):
                st.session_state.master_sheet_verified = True
                st.success(f"✓ Master sheet exists")
            else:
                st.session_state.master_sheet_verified = False
                st.error(f"✗ Master sheet not found")
        else:
            st.session_state.master_sheet_verified = False
            st.warning("Please enter a file path")

# Data directory count checker
st.subheader("Data Directory Checker")
col1, col2 = st.columns([4, 1])

with col1:
    data_dir_path = st.text_input("Data directory path:", placeholder="Enter the path to your data directory")

with col2:
    st.write("")
    if st.button("Count files"):
        if data_dir_path:
            if os.path.isdir(data_dir_path):
                file_count = sum(
                    1 for entry in os.scandir(data_dir_path) if entry.is_file()
                )
                st.session_state.data_dir_count = file_count
                st.success(f"✓ {file_count} files found in data directory")
            else:
                st.session_state.data_dir_count = None
                st.error(f"✗ Data directory not found")
        else:
            st.session_state.data_dir_count = None
            st.warning("Please enter a directory path")

if st.session_state.data_dir_count is not None:
    st.info(f"Number of files: {st.session_state.data_dir_count}")

st.divider()

# Job submission section
st.subheader("SLURM Job Submission")

if not st.session_state.master_sheet_verified:
    st.warning("⚠️ Please verify the master sheet first to launch jobs")

job = st.selectbox("Select pipeline stage", [
    "1-Denoising",
    "2-Segmentation",
    "3-Weight Checking",
    "4-Sampling",
    "5-Feature Extraction",
    "6-Merging data",
])

submit_button = st.button("Submit SLURM job", disabled=not st.session_state.master_sheet_verified)

if submit_button:
    slurm_script = f"slurm/{job}.slurm"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(
        hostname="YOUR_HPC_ADDRESS",
        username="YOUR_USERNAME",
        key_filename="~/.ssh/id_ed25519"
    )

    cmd = f"sbatch {slurm_script}"
    stdin, stdout, stderr = ssh.exec_command(cmd)

    output = stdout.read().decode()
    error = stderr.read().decode()

    st.text(output)
    st.text(error)
