import streamlit as st

STAGE_NAME = "2-Segmentation"

def render(config):
    st.subheader(STAGE_NAME)
    st.write("Use this page to design the segmentation stage.")
    st.write(f"Master sheet: {config['master_sheet_path']}")
    st.write(f"Data directory: {config['data_directory_path']}")
    st.write(f"File count: {config['file_count']}")

    model_choice = st.selectbox("Segmentation model", ["U-Net", "Mask R-CNN", "Custom"])
    threshold = st.slider("Confidence threshold", 0.0, 1.0, 0.5)
    st.write(f"Selected model: {model_choice}, threshold: {threshold}")

    if st.button("Save segmentation settings"):
        st.success("Segmentation settings saved.")
