import streamlit as st

STAGE_NAME = "6-Merging data"

def render(config):
    st.subheader(STAGE_NAME)
    st.write("Use this page to design the data merging stage.")
    st.write(f"Master sheet: {config['master_sheet_path']}")
    st.write(f"Data directory: {config['data_directory_path']}")
    st.write(f"File count: {config['file_count']}")

    merge_strategy = st.selectbox("Merge strategy", ["Concatenate", "Aggregate", "Join by ID"])
    output_name = st.text_input("Output filename", "merged_output.csv")
    st.write(f"Selected strategy: {merge_strategy}, output file: {output_name}")

    if st.button("Save merging settings"):
        st.success("Merging settings saved.")
