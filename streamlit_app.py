import streamlit as st
import pandas as pd
from datetime import date
import altair as alt
import plotly.express as px

st.set_page_config(
    page_title="End To End Tracking Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded")

alt.themes.enable("dark")


# Define well names
wells = ["Well Alpha", "Well Bravo", "Well Charlie", "Well Delta", "Well Echo", "Well Foxtrot", "Well Golf", "Well Hotel", "Well India", "Well Juliet"]

# Define process stages
processes = [
    "WLCTF_ UWO ➜ GGO",
    "Standalone Activity",
    "On Plot HookUp",
    "Pre-commissioning",
    "Unhook",
    "WLCTF_ GGO ➜ UWIF",
    "Waiting on IFS Resources",
    "Frac Execution",
    "Re-Hook & commissioning",
    "Plug Removal",
    "On stream"
]

# Data storage
if 'data' not in st.session_state:
    st.session_state['data'] = {well: {process: {'start': None, 'end': None} for process in processes} for well in wells}

# Layout
st.sidebar.header("Well Selection and Data Entry")
selected_well = st.sidebar.selectbox("Select a Well", wells)

st.sidebar.markdown(f"### Enter Dates for {selected_well}")

# Ensure that when a new well is selected, date inputs are cleared
for process in processes:
    if st.session_state['data'][selected_well][process]['start'] is None:
        start_date = None
    else:
        start_date = st.session_state['data'][selected_well][process]['start']

    if st.session_state['data'][selected_well][process]['end'] is None:
        end_date = None
    else:
        end_date = st.session_state['data'][selected_well][process]['end']

    st.sidebar.markdown(f"**{process}**")
    col_start, col_end = st.sidebar.columns(2)
    with col_start:
        st.write("Start")
        start_date = st.date_input(
            f"Start - {process}",
            value=start_date,
            label_visibility="collapsed"
        )
    with col_end:
        st.write("End")
        end_date = st.date_input(
            f"End - {process}",
            value=end_date,
            label_visibility="collapsed"
        )

    st.session_state['data'][selected_well][process]['start'] = start_date
    st.session_state['data'][selected_well][process]['end'] = end_date

# Columns for visualization
col1, col2, col3 = st.columns(3)

# Column 1: Well being updated
col1.header(f"Well: {selected_well}")
for process, dates in st.session_state['data'][selected_well].items():
    start_date = dates['start']
    end_date = dates['end']
    if start_date and end_date:
        duration = max((end_date - start_date).days, 1)
        col1.write(f"{process}: {duration} days")
    else:
        col1.write(f"{process}: Incomplete")

# Column 2: KPI Visualization and Comparison
col2.header("KPI Visualization and Comparison")

# Collect data for all wells for visualization
chart_data = []
for well, well_data in st.session_state['data'].items():
    for process, dates in well_data.items():
        start_date = dates['start']
        end_date = dates['end']
        if start_date and end_date:
            duration = max((end_date - start_date).days, 1)
            chart_data.append({'Well': well, 'Process': process, 'Duration': duration})

# Create DataFrame for visualization
chart_df = pd.DataFrame(chart_data)

if not chart_df.empty:
    fig = px.bar(chart_df, x='Process', y='Duration', color='Well', barmode='group', title="Process Duration Comparison")
    col2.plotly_chart(fig)
else:
    col2.write("Enter dates to generate the comparison chart.")

# Column 3: Gaps, Lagging, and Leading
col3.header("Gaps, Lagging, and Leading")

# Gap Analysis
for process, dates in st.session_state['data'][selected_well].items():
    start_date = dates['start']
    end_date = dates['end']
    if start_date and end_date:
        if end_date < start_date:
            col3.write(f"Error: {process} end date is before start date")
    elif not start_date or not end_date:
        col3.write(f"{process}: Dates not fully entered")
