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


if "data" not in st.session_state:
    # Initialize empty data structure with None dates
    st.session_state["data"] = {}
    for well in wells:
        st.session_state["data"][well] = {}
        for p in processes:
            st.session_state["data"][well][p] = {"start": None, "end": None}

st.title("End-to-End Process Tracker")

# Sidebar: Well selector
selected_well = st.sidebar.selectbox("Select Well", wells)

st.sidebar.markdown("### Rig Release Date")
rig_release_col1, rig_release_col2 = st.sidebar.columns([1, 3])
with rig_release_col1:
    st.write("Date")
with rig_release_col2:
    rig_release_date = st.date_input(
        "Rig Release",
        value=st.session_state['data'][selected_well]['Rig Release']['start'] or date.today(),
        key=f"{selected_well}_RigRelease",
        label_visibility="collapsed"
    )
# Update session state for Rig Release start and end (same date)
st.session_state['data'][selected_well]['Rig Release']['start'] = rig_release_date
st.session_state['data'][selected_well]['Rig Release']['end'] = rig_release_date

st.sidebar.markdown("---")

# Sidebar: process dates input (excluding Rig Release)
for process in [p for p in processes if p != "Rig Release"]:
    st.sidebar.markdown(f"### {process}")
    col1, col2 = st.sidebar.columns([1, 1])
    start_val = st.session_state['data'][selected_well][process]['start']
    end_val = st.session_state['data'][selected_well][process]['end']

    with col1:
        start_date = st.date_input(
            f"{process} Start",
            value=start_val or date.today(),
            key=f"{selected_well}_{process}_start",
            label_visibility="visible"
        )
    with col2:
        end_date = st.date_input(
            f"{process} End",
            value=end_val or date.today(),
            key=f"{selected_well}_{process}_end",
            label_visibility="visible"
        )
    # Validate
    if start_date > end_date:
        st.sidebar.error(f"Start date must be before or equal to End date for **{process}**")
    else:
        st.session_state['data'][selected_well][process]['start'] = start_date
        st.session_state['data'][selected_well][process]['end'] = end_date

# Main page layout: 3 columns with width ratio 1.5, 4.5, 2
col1, col2, col3 = st.columns((1.5, 4.5, 2), gap="medium")

# Column 1: Show total days per process for selected well
col1.header(f"Process Durations for {selected_well}")
durations = []
for process, dates in st.session_state['data'][selected_well].items():
    # Skip processes without both dates
    if dates['start'] and dates['end']:
        delta = (dates['end'] - dates['start']).days
        delta = max(delta, 1)  # Minimum 1 day if same day
        durations.append((process, delta))
    else:
        durations.append((process, None))

# Display as dataframe
df_col1 = pd.DataFrame(durations, columns=["Process", "Duration (days)"])
col1.dataframe(df_col1, use_container_width=True)

# Column 2: KPI Visualization and Comparison
col2.header("KPI Comparison Across Wells")

# Prepare data for chart excluding Rig Release
chart_data = []
for well in wells:
    for process, dates in st.session_state['data'][well].items():
        if process == "Rig Release":
            continue
        if dates['start'] and dates['end']:
            duration = max((dates['end'] - dates['start']).days, 1)
            chart_data.append({"Well": well, "Process": process, "Duration": duration})

df_chart = pd.DataFrame(chart_data)

if not df_chart.empty:
    import altair as alt
    chart = (
        alt.Chart(df_chart)
        .mark_bar()
        .encode(
            x=alt.X('Duration:Q', title='Duration (days)'),
            y=alt.Y('Process:N', sort=processes[1:], title='Process'),
            color='Well:N',
            tooltip=['Well', 'Process', 'Duration']
        )
        .properties(height=400)
    )
    col2.altair_chart(chart, use_container_width=True)
else:
    col2.write("No data to display.")

# Column 3: Progress Overview
col3.header("Progress Overview")

progress_data = []
for well, well_data in st.session_state['data'].items():
    rig_release_start = well_data['Rig Release']['start']
    on_stream_end = well_data['On stream']['end']
    if rig_release_start and on_stream_end:
        total_days = max((on_stream_end - rig_release_start).days, 1)
        progress_pct = min((total_days / 120) * 100, 100)
        progress_data.append({"Well": well, "Total Days": total_days, "Progress (%)": progress_pct})

progress_df = pd.DataFrame(progress_data)
if not progress_df.empty:
    # Sort descending and rank starting at 1
    progress_df = progress_df.sort_values("Total Days", ascending=False).reset_index(drop=True)
    progress_df.index += 1
    col3.dataframe(
        progress_df,
        use_container_width=True,
        column_config={
            "Progress (%)": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="{:.1f}%",
                label="Completion"
            )
        }
    )
else:
    col3.write("No data available for progress overview.")
