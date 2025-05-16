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

# Well selection
selected_well = st.selectbox("Select a Well", wells)

st.markdown(f"### Enter Dates for {selected_well}")

# Date inputs
for process in processes:
    st.session_state['data'][selected_well][process] = st.date_input(
        process, value=date.today()
    )

# Display progress tracking
st.markdown(f"### Progress Tracking for {selected_well}")
progress_data = st.session_state['data'][selected_well]
completed_processes = sum(1 for date in progress_data.values() if date)
total_processes = len(processes)
progress_percentage = completed_processes / total_processes

st.progress(progress_percentage)

# KPI Comparison
st.markdown("### KPI Comparison")
# Placeholder for future KPI tracking logic
st.write("KPI tracking will be implemented here.")
