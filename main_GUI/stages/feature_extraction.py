import streamlit as st

STAGE_NAME = "5-Feature Extraction"

def render(config):
    st.subheader(STAGE_NAME)
    st.write("Use this page to design the feature extraction stage.")
    st.write(f"Master sheet: {config['master_sheet_path']}")
    st.write(f"Data directory: {config['data_directory_path']}")
    st.write(f"File count: {config['file_count']}")

    feature_set = st.multiselect("Feature set", ["Shape", "Texture", "Intensity", "Frequency"])
    st.write(f"Selected features: {feature_set}")

    if st.button("Save feature extraction settings"):
        st.success("Feature extraction settings saved.")
