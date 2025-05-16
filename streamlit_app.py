import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
import altair as alt
import plotly.express as px

st.set_page_config(
    page_title="End To End Tracking Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded")

alt.themes.enable("dark")

# Database setup
DB_PATH = 'tracking_data.db'
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# Create table if not exists
c.execute('''CREATE TABLE IF NOT EXISTS process_data (
    well TEXT,
    process TEXT,
    start_date TEXT,
    end_date TEXT,
    PRIMARY KEY (well, process)
)''')
conn.commit()

# Define user roles
USERS = {
    "user1": "entry",
    "user2": "entry",
    "user3": "entry",
    "viewer1": "view",
    "viewer2": "view",
    "viewer3": "view"
}

# User Authentication
username = st.sidebar.text_input("Username")
if username not in USERS:
    st.sidebar.error("User not recognized")
    st.stop()

role = USERS[username]

# Define well names
wells = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliet"]

# Define process stages
processes = [
    "Rig Release",
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

# Layout
st.sidebar.header("Well Selection and Data Entry")
previous_well = st.session_state.get('selected_well', None)
selected_well = st.sidebar.selectbox("Select a Well", wells)
st.session_state['selected_well'] = selected_well

# Function to load well data from DB into session_state
def load_well_data(well):
    for process in processes:
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, process))
        result = c.fetchone()
        if result:
            start = pd.to_datetime(result[0]).date() if result[0] else None
            end = pd.to_datetime(result[1]).date() if result[1] else None
            st.session_state[f"start_{process}"] = start
            st.session_state[f"end_{process}"] = end
        else:
            st.session_state[f"start_{process}"] = None
            st.session_state[f"end_{process}"] = None

# Clear or load data on well change
if previous_well != selected_well:
    load_well_data(selected_well)

if role == "entry":
    # Rig Release - Single Date Input in sidebar (side by side)
    st.sidebar.markdown("**Rig Release Date**")
    col_rr_date, col_rr_input = st.sidebar.columns([1, 2])
    with col_rr_date:
        st.markdown("Rig Release")
    with col_rr_input:
        rig_release_key = "start_Rig Release"
        rig_release_date = st.date_input(
            label="",
            key=rig_release_key,
            value=st.session_state.get(rig_release_key, None),
            label_visibility="collapsed"
        )
        # Save Rig Release as both start and end date equal
        if rig_release_date:
            c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                      (selected_well, "Rig Release", rig_release_date.isoformat(), rig_release_date.isoformat()))
            conn.commit()
            st.session_state[f"end_Rig Release"] = rig_release_date

    # Process Data Entry for other processes
    for process in processes[1:]:
        st.sidebar.markdown(f"**{process}**")
        col_start, col_end = st.sidebar.columns(2)

        start_date_key = f"start_{process}"
        end_date_key = f"end_{process}"

        # Get dates from session state or None
        start_date_val = st.session_state.get(start_date_key, None)
        end_date_val = st.session_state.get(end_date_key, None)

        with col_start:
            start_date = st.date_input(
                label="Start",
                key=start_date_key,
                value=start_date_val,
                label_visibility="visible",
            )
            if start_date is None:
                st.markdown("_Add a date_")

        with col_end:
            end_date = st.date_input(
                label="End",
                key=end_date_key,
                value=end_date_val,
                label_visibility="visible",
            )
            if end_date is None:
                st.markdown("_Add a date_")

        # Validation and save
        if start_date and end_date:
            if end_date < start_date:
                st.sidebar.error(f"Error: End date cannot be earlier than Start date for {process}.")
            else:
                c.execute(
                    'REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                    (selected_well, process, start_date.isoformat(), end_date.isoformat())
                )
                conn.commit()
        else:
            st.sidebar.info(f"Please enter both start and end dates for {process} to save.")

# Columns for visualization
col1, col2, col3 = st.columns((1.5, 4.5, 2), gap='medium')

# Column 1: Well being updated (exclude Rig Release)
col1.header(f"Well: {selected_well}")
if role in ["view", "entry"]:
    for process in processes[1:]:
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
        result = c.fetchone()
        if result and result[0] and result[1]:
            duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
            col1.write(f"{process}: {duration} days")
        else:
            col1.write(f"{process}: Incomplete")

# Column 2: KPI Visualization and Comparison (exclude Rig Release)
col2.header("KPI Visualization and Comparison")
chart_data = []
for well in wells:
    for process in processes[1:]:
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, process))
        result = c.fetchone()
        if result and result[0] and result[1]:
            duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
            chart_data.append({'Well': well, 'Process': process, 'Duration': duration})

chart_df = pd.DataFrame(chart_data)
if not chart_df.empty:
    fig = px.bar(chart_df, x='Process', y='Duration', color='Well', barmode='group')
    col2.plotly_chart(fig)

# Column 3: Progress Overview & Gap Analysis
col3.header("Progress Overview & Gaps Analysis")
progress_data = []
gap_analysis = []
for well in wells:
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig_release = c.fetchone()
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    on_stream = c.fetchone()
    if rig_release and rig_release[0] and on_stream and on_stream[1]:
        total_days = max((pd.to_datetime(on_stream[1]) - pd.to_datetime(rig_release[0])).days, 1)
        progress = (total_days / 120) * 100
        color = "#32CD32" if total_days <= 120 else "#FF6347"
        progress_data.append({"Well": well, "Total Days": total_days, "Progress": progress, "Color": color})
        gap = total_days - 120
        gap_analysis.append(f"{well}: {'Over' if gap > 0 else 'Under'} target by {abs(gap)} days")

progress_df = pd.DataFrame(progress_data)
if not progress_df.empty:
    # We add a colored progress bar column in dataframe display using column_config param
    col3.dataframe(
        progress_df,
        use_container_width=True,
        column_config={
            "Well": st.column_config.TextColumn("Well"),
            "Total Days": st.column_config.NumberColumn("Total Days"),
            "Progress": st.column_config.ProgressColumn(
                "Progress %",
                format="%0.1f%%",
                min_value=0,
                max_value=None,  # no cap to allow > 100%
                help="Progress (Total Days / 120 * 100%)",
                bar_color=lambda val: "#32CD32" if val <= 100 else "#FF6347",
            ),
            "Color": st.column_config.HiddenColumn()
        }
    )

if gap_analysis:
    col3.write("### Gap Analysis")
    for gap in gap_analysis:
        col3.write(gap)
