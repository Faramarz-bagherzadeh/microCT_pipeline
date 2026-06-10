import streamlit as st

STAGE_NAME = "3-Weight Checking"

def render(config):
    st.subheader(STAGE_NAME)
    st.write("Use this page to design the weight checking stage.")
    st.write(f"Master sheet: {config['master_sheet_path']}")
    st.write(f"Data directory: {config['data_directory_path']}")
    st.write(f"File count: {config['file_count']}")

    check_method = st.selectbox("Weight check method", ["Simple", "Advanced", "Threshold-based"])
    tolerance = st.number_input("Tolerance (grams)", min_value=0.0, value=0.1)
    st.write(f"Selected method: {check_method}, tolerance: {tolerance}")

    if st.button("Save weight checking settings"):
        st.success("Weight checking settings saved.")
