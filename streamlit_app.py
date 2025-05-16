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

# Layout
st.sidebar.header("Well Selection and Data Entry")
previous_well = st.session_state.get('selected_well', None)
selected_well = st.sidebar.selectbox("Select a Well", wells)
st.session_state['selected_well'] = selected_well

# Clear unsaved data entries if a new well is selected
if previous_well != selected_well:
    for process in processes:
        key_start = f"start_{process}"
        key_end = f"end_{process}"
        # Load saved data from DB for selected well and process
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
        result = c.fetchone()
        if result:
            start_val = pd.to_datetime(result[0]).date() if result[0] else None
            end_val = pd.to_datetime(result[1]).date() if result[1] else None
        else:
            start_val = None
            end_val = None

        # If session state has unsaved changes (i.e. different from DB), clear them
        # For simplicity, always reset widget state to saved DB values or None
        st.session_state[key_start] = start_val
        st.session_state[key_end] = end_val

if role == "entry":
    # Rig Release - Single Date Input
    rig_release_key = "rig_release"
    default_rig_release = st.session_state.get(rig_release_key, date.today())
    rig_release_date = st.sidebar.date_input(
        "Rig Release",
        value=default_rig_release,
        key=rig_release_key,
        help="Enter Rig Release Date"
    )

    # Save Rig Release immediately (start_date = end_date for rig release)
    c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
              (selected_well, "Rig Release", rig_release_date.isoformat(), rig_release_date.isoformat()))
    conn.commit()

    # Also keep end date session state consistent for Rig Release
    st.session_state[f"end_Rig Release"] = rig_release_date

    # Process Data Entry for other processes
    for process in processes[1:]:
        key_start = f"start_{process}"
        key_end = f"end_{process}"
        st.sidebar.markdown(f"**{process}**")
        col_start, col_end = st.sidebar.columns(2)

        with col_start:
            # Provide default value from session state or fallback
            default_start = st.session_state.get(key_start, None)
            start_date = st.date_input(f"Start - {process}", value=default_start, key=key_start)

        with col_end:
            default_end = st.session_state.get(key_end, None)
            end_date = st.date_input(f"End - {process}", value=default_end, key=key_end)

        # Validation: Start date must be before or equal end date
        if start_date and end_date and start_date > end_date:
            st.sidebar.error(f"Error: Start date must be before or equal to End date for {process}")
        else:
            # Save to DB immediately if valid
            if start_date and end_date:
                c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                          (selected_well, process, start_date.isoformat(), end_date.isoformat()))
                conn.commit()

# Visualization columns
col1, col2, col3 = st.columns((1.5, 4.5, 2), gap='medium')

# Column 1: Well being updated (exclude Rig Release)
col1.header(f"Well: {selected_well}")
for process in processes[1:]:
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
    result = c.fetchone()
    if result and result[0] and result[1]:
        duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
        col1.write(f"{process}: {duration} days")
    else:
        col1.write(f"{process}: Add dates")

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
col3.header("Progress Overview & Gap Analysis")

progress_data = []
gap_analysis = []
for well in wells:
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig_release = c.fetchone()
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    on_stream = c.fetchone()
    if rig_release and rig_release[0] and on_stream and on_stream[1]:
        total_days = max((pd.to_datetime(on_stream[1]) - pd.to_datetime(rig_release[0])).days, 1)
        progress = (total_days / 120) * 100  # percentage, can go above 100%
        color = "#32CD32" if total_days <= 120 else "#FF6347"
        progress_data.append({"Well": well, "Total Days": total_days, "Progress": progress, "Color": color})
        gap = total_days - 120
        gap_analysis.append(f"{well}: {'Over' if gap > 0 else 'Under'} target by {abs(gap)} days")
    else:
        progress_data.append({"Well": well, "Total Days": None, "Progress": None, "Color": None})
        gap_analysis.append(f"{well}: Missing Rig Release or On stream dates")

progress_df = pd.DataFrame(progress_data)

if not progress_df.empty:
    # Show colored progress column
    def color_progress(val, color):
        return f'background-color: {color}' if color else ''

    # Prepare dataframe for display without the color column
    display_df = progress_df.drop(columns=["Color"]).copy()
    # Style the progress column with colors
    styled_df = display_df.style.apply(
        lambda x: [color_progress(v, progress_df.loc[x.name, "Color"]) for v in x],
        axis=1
    )
    col3.dataframe(styled_df, use_container_width=True)

col3.write("### Gap Analysis")
for gap in gap_analysis:
    col3.write(gap)
