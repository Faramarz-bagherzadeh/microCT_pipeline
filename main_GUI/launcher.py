import streamlit as st
import os
import subprocess
import json
from stages import denoising, segmentation, weight_checking, sampling, feature_extraction, merging_data

st.title("Micro CT pipe line")

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
config_file_path = os.path.join(script_dir, "config.json")

# Initialize session state for master sheet verification and data directory count
if "master_sheet_verified" not in st.session_state:
    st.session_state.master_sheet_verified = False
if "data_dir_count" not in st.session_state:
    st.session_state.data_dir_count = None
if "master_sheet_abs_path" not in st.session_state:
    st.session_state.master_sheet_abs_path = None
if "data_dir_abs_path" not in st.session_state:
    st.session_state.data_dir_abs_path = None
if "stage_selection_enabled" not in st.session_state:
    st.session_state.stage_selection_enabled = False
if "active_stage" not in st.session_state:
    st.session_state.active_stage = None
if "selected_stage" not in st.session_state:
    st.session_state.selected_stage = "1-Denoising"


def save_config():
    config_data = {
        "master_sheet_path": st.session_state.master_sheet_abs_path,
        "data_directory_path": st.session_state.data_dir_abs_path,
        "file_count": st.session_state.data_dir_count
    }
    try:
        with open(config_file_path, "w") as f:
            json.dump(config_data, f, indent=4)
        return True
    except PermissionError:
        st.error(f"✗ Permission denied: Cannot write to {config_file_path}")
    except IOError as e:
        st.error(f"✗ Error writing config file: {e}")
    return False


st.subheader("Path Configuration")
col1, col2 = st.columns(2)

with col1:
    master_sheet_path = st.text_input("Master sheet file path:", placeholder="Enter the path to your master sheet file")
with col2:
    data_dir_path = st.text_input("Data directory path:", placeholder="Enter the path to your data directory")

if st.button("Verify Paths", use_container_width=True):
    if not master_sheet_path or not data_dir_path:
        st.error("✗ Please enter both paths")
        st.session_state.master_sheet_verified = False
        st.session_state.data_dir_count = None
        st.session_state.stage_selection_enabled = False
        st.session_state.active_stage = None
    elif not os.path.exists(master_sheet_path):
        st.error("✗ Master sheet file not found")
        st.session_state.master_sheet_verified = False
        st.session_state.data_dir_count = None
        st.session_state.stage_selection_enabled = False
        st.session_state.active_stage = None
    elif not os.path.isdir(data_dir_path):
        st.error("✗ Data directory not found")
        st.session_state.master_sheet_verified = False
        st.session_state.data_dir_count = None
        st.session_state.stage_selection_enabled = False
        st.session_state.active_stage = None
    else:
        file_count = sum(
            1 for entry in os.scandir(data_dir_path) if entry.is_file()
        )
        st.session_state.master_sheet_verified = True
        st.session_state.data_dir_count = file_count
        st.session_state.master_sheet_abs_path = os.path.abspath(master_sheet_path)
        st.session_state.data_dir_abs_path = os.path.abspath(data_dir_path)
        st.session_state.stage_selection_enabled = True
        st.session_state.active_stage = None

        if save_config():
            st.success("✓ Paths verified and saved to config.json")
            st.info(f"Master sheet: {st.session_state.master_sheet_abs_path}")
            st.info(f"Data directory: {st.session_state.data_dir_abs_path} ({file_count} files)")

if st.session_state.master_sheet_verified:
    st.success("✓ Paths already verified")
    st.info(f"Master sheet: {st.session_state.master_sheet_abs_path}")
    st.info(f"Data directory: {st.session_state.data_dir_abs_path} ({st.session_state.data_dir_count} files)")

STAGE_MODULES = {
    "1-Denoising": denoising,
    "2-Segmentation": segmentation,
    "3-Weight Checking": weight_checking,
    "4-Sampling": sampling,
    "5-Feature Extraction": feature_extraction,
    "6-Merging data": merging_data,
}

if st.session_state.stage_selection_enabled:
    st.divider()
    st.subheader("Stage Selection")
    st.session_state.selected_stage = st.selectbox("Pipeline stage", list(STAGE_MODULES.keys()), index=list(STAGE_MODULES.keys()).index(st.session_state.selected_stage))

    if st.button("Open stage", use_container_width=True):
        st.session_state.active_stage = st.session_state.selected_stage

if st.session_state.active_stage:
    st.divider()
    stage = st.session_state.active_stage
    stage_module = STAGE_MODULES.get(stage)
    if stage_module is not None:
        config = {
            "master_sheet_path": st.session_state.master_sheet_abs_path,
            "data_directory_path": st.session_state.data_dir_abs_path,
            "file_count": st.session_state.data_dir_count,
        }
        stage_module.render(config)
    else:
        st.error(f"Unknown stage: {stage}")

    st.markdown("---")
    if st.button("Back to stage selection"):
        st.session_state.active_stage = None
    if st.button("Reset verification"):
        st.session_state.master_sheet_verified = False
        st.session_state.data_dir_count = None
        st.session_state.master_sheet_abs_path = None
        st.session_state.data_dir_abs_path = None
        st.session_state.stage_selection_enabled = False
        st.session_state.active_stage = None

