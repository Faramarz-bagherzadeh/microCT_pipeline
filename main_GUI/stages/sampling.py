import streamlit as st

STAGE_NAME = "4-Sampling"

def render(config):
    st.subheader(STAGE_NAME)
    st.write("Use this page to design the sampling stage.")
    st.write(f"Master sheet: {config['master_sheet_path']}")
    st.write(f"Data directory: {config['data_directory_path']}")
    st.write(f"File count: {config['file_count']}")

    sample_rate = st.slider("Sample rate (%)", 1, 100, 10)
    random_seed = st.number_input("Random seed", value=42)
    st.write(f"Selected sample rate: {sample_rate}%, random seed: {random_seed}")

    if st.button("Save sampling settings"):
        st.success("Sampling settings saved.")
