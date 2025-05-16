import streamlit as st
import pandas as pd
from datetime import date

st.set_page_config(layout="wide")

# Define well names
wells = [f"Well {chr(65 + i)}" for i in range(10)]

# Define process stages
processes = [
    "Handover WLCTF from UWO to GGO",
    "Standalone Activity (SCMT Execution)",
    "On Plot Mechanical Completion",
    "Pre-commissioning (up to SOF)",
    "Unhook",
    "Handover WLCTF from GGO to UWI",
    "Waiting on shared IFS resources",
    "Frac Execution",
    "Re-Hook and commissioning (eSOF)",
    "Plug Removal",
    "On stream"
]

# Data storage
if 'data' not in st.session_state:
    st.session_state['data'] = {well: {process: None for process in processes} for well in wells}

# Layout
st.sidebar.header("Well Selection and Data Entry")
selected_well = st.sidebar.selectbox("Select a Well", wells)

st.sidebar.markdown(f"### Enter Dates for {selected_well}")
for process in processes:
    st.session_state['data'][selected_well][process] = st.sidebar.date_input(
        process, value=date.today()
    )

# Columns for visualization
col1, col2, col3 = st.columns(3)

# Column 1: Well being updated
col1.header(f"Well: {selected_well}")
for process, process_date in st.session_state['data'][selected_well].items():
    col1.write(f"{process}: {process_date}")

# Column 2: KPI Visualization and Comparison
col2.header("KPI Visualization and Comparison")
# Placeholder for future visualization logic
col2.write("Visualization to be added.")

# Column 3: Gaps, Lagging, and Leading
col3.header("Gaps, Lagging, and Leading")
# Placeholder for gap analysis logic
col3.write("Gap analysis to be added.")
