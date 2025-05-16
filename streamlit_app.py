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
wells = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliet"]

# Define process stages
processes = ["Rig Release",
    "WLCTF_ UWO ➜ GGO",
    "Standalone Activity",
    "On Plot Hookup",
    "Pre-commissioning",
    "Unhook",
    "WLCTF_GGO ➜ UWIF",
    "Waiting IFS Resources",
    "Frac Execution",
    "Re-Hook & commissioning",
    "Plug Removal",
    "On stream"
]
####################################################################


# Data storage
if 'data' not in st.session_state:
    st.session_state['data'] = {well: {process: {'start': None, 'end': None} for process in processes} for well in wells}

# Layout
st.sidebar.header("Well Selection and Data Entry")
selected_well = st.sidebar.selectbox("Select a Well", wells)

st.sidebar.markdown(f"### Enter Dates for {selected_well}")

# Rig Release as a single input - Side-by-Side Layout
st.sidebar.markdown("**Rig Release Date**")
rig_release_col1, rig_release_col2 = st.sidebar.columns([1, 3])
with rig_release_col1:
    st.write("Date")
with rig_release_col2:
    rig_release_date = st.date_input(
        "Rig Release",
        value=st.session_state['data'][selected_well]['Rig Release']['start'],
        label_visibility="collapsed"
    )
st.session_state['data'][selected_well]['Rig Release']['start'] = rig_release_date
st.session_state['data'][selected_well]['Rig Release']['end'] = rig_release_date


# Ensure that when a new well is selected, date inputs are cleared
for process in [p for p in processes if p != 'Rig Release']:
    start_date = st.session_state['data'][selected_well][process]['start']
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

    # Validation
    if start_date and end_date and start_date > end_date:
        st.sidebar.error(f"Error: Start date must be before End date for {process}")
    st.session_state['data'][selected_well][process]['start'] = start_date
    st.session_state['data'][selected_well][process]['end'] = end_date


# Columns for visualization
col1, col2, col3 = st.columns((1.5, 4.5, 2), gap='medium')

# Column 1: Well being updated
col1.header(f"Well: {selected_well}")
for process, dates in st.session_state['data'][selected_well].items():
    if process == 'Rig Release':
        continue
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
            if process != 'Rig Release':
                chart_data.append({'Well': well, 'Process': process, 'Duration': duration})

chart_df = pd.DataFrame(chart_data)

if not chart_df.empty:
    fig = px.bar(chart_df, x='Process', y='Duration', color='Well', barmode='group', title="Process Duration Comparison")
    col2.plotly_chart(fig)
else:
    col2.write("Enter dates to generate the comparison chart.")


# Column 3: Progress Overview and Gaps
col3.header("Progress Overview")
progress_data = []
gap_messages = []

for well, well_data in st.session_state['data'].items():
    rig_release_start = well_data['Rig Release']['start']
    on_stream_end = well_data['On stream']['end']
    if rig_release_start and on_stream_end:
        total_days = max((on_stream_end - rig_release_start).days, 1)
        completion_days = total_days - 120
        progress_percentage = min((total_days / 120) * 100, 100)
        progress_data.append({"Well": well, "Total Days": total_days, "Completion Days": completion_days, "Progress": progress_percentage})

    # Gap Analysis for selected well
    if well == selected_well:
        for process, dates in well_data.items():
            start_date = dates['start']
            end_date = dates['end']
            if start_date and end_date and end_date < start_date:
                gap_messages.append(f"Error: {process} end date is before start date")
            elif not start_date or not end_date:
                gap_messages.append(f"{process}: Dates not fully entered")

# Display Progress Overview
progress_df = pd.DataFrame(progress_data)

if not progress_df.empty:
    col3.dataframe(
        progress_df,
        use_container_width=True,
        column_config={
            "Progress": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="{:.1f}%",
                label="Completion"
            )
        }
    )
else:
    col3.write("No data available for progress tracking.")

# Display Gap Analysis
col3.header("Gaps, Lagging, and Leading")
for msg in gap_messages:
    col3.write(msg)
