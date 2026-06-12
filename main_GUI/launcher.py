import streamlit as st
import os
import json
from stages import denoising, segmentation, weight_checking, sampling, feature_extraction, merging_data

st.title("Micro CT pipe line")

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
config_file_path = os.path.join(script_dir, "config.json")


def load_config():
    default_config = {
        "master_sheet_path": None,
        "data_directory_path": None,
        "file_count": None,
    }
    if os.path.exists(config_file_path):
        try:
            with open(config_file_path, "r") as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                default_config.update(stored)
        except Exception:
            pass
    return default_config


config = load_config()

if "active_stage" not in st.session_state:
    st.session_state.active_stage = None
if "selected_stage" not in st.session_state:
    st.session_state.selected_stage = "1-Denoising"

STAGE_MODULES = {
    "1-Denoising": denoising,
    "2-Segmentation": segmentation,
    "3-Weight Checking": weight_checking,
    "4-Sampling": sampling,
    "5-Feature Extraction": feature_extraction,
    "6-Merging data": merging_data,
}

st.subheader("Stage Selection")
st.session_state.selected_stage = st.selectbox(
    "Pipeline stage",
    list(STAGE_MODULES.keys()),
    index=list(STAGE_MODULES.keys()).index(st.session_state.selected_stage),
)

if st.button("Open stage", use_container_width=True):
    st.session_state.active_stage = st.session_state.selected_stage

if st.session_state.active_stage:
    st.divider()
    stage = st.session_state.active_stage
    stage_module = STAGE_MODULES.get(stage)
    if stage_module is not None:
        stage_module.render(config)
    else:
        st.error(f"Unknown stage: {stage}")

    st.markdown("---")
    if st.button("Back to stage selection"):
        st.session_state.active_stage = None

