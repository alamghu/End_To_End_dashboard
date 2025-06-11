import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime
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
wells = ["SNN-11", "SN-113", "SN-114", "SNN-10", "SR-603", "SN-115", "BRNW-106", "SNNORTH11_DEV", "SRM-V36A", "SRM-VE127"]

# Define process stages
processes = [
    "Rig Release",
    "WLCTF_ UWO ➔ GGO",
    "Standalone Activity",
    "On Plot Hookup",
    "Pre-commissioning",
    "Unhook",
    "WLCTF_GGO ➔ UWIF",
    "Waiting IFS Resources",
    "Frac Execution",
    "Re-Hook & commissioning",
    "Plug Removal",
    "On stream"
]

# Sidebar - Well Selection
st.sidebar.header("Well Selection and Data Entry")
selected_well = st.sidebar.selectbox("Select a Well", wells)

# Load existing data into session_state
for process in processes:
    key_start = f"start_{process}"
    key_end = f"end_{process}"
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
    result = c.fetchone()
    st.session_state[key_start] = pd.to_datetime(result[0]).date() if result and result[0] else None
    st.session_state[key_end] = pd.to_datetime(result[1]).date() if result and result[1] else None

if role == "entry":
    # Rig Release Entry - only if already saved for that well
    rig_release_key = "end_Rig Release"
    if st.session_state[rig_release_key]:
        rig_release_default = st.session_state[rig_release_key]
    else:
        rig_release_default = None

    rig_release_date = st.sidebar.date_input("Rig Release", value=rig_release_default or date.today(), key="rig_release")
    if rig_release_date:
        c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                  (selected_well, "Rig Release", rig_release_date.isoformat(), rig_release_date.isoformat()))
        conn.commit()
        st.session_state[f"end_Rig Release"] = rig_release_date

    for process in processes[1:]:
        key_start = f"start_{process}"
        key_end = f"end_{process}"
        st.sidebar.markdown(f"**{process}**")
        col_start, col_end = st.sidebar.columns(2)

        with col_start:
            start_default = st.session_state[key_start] or date.today()
            start_date = st.date_input(f"Start - {process}", value=start_default, key=key_start)

        with col_end:
            end_default = st.session_state[key_end] or date.today()
            end_date = st.date_input(f"End - {process}", value=end_default, key=key_end)

        if start_date and end_date and start_date > end_date:
            st.sidebar.error(f"Error: Start date must be before or equal to End date for {process}")
        elif start_date and end_date:
            c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                      (selected_well, process, start_date.isoformat(), end_date.isoformat()))
            conn.commit()

# Layout Columns
col1, col2, col3 = st.columns((1.5, 4.5, 2), gap='medium')

# Column 1: Process Duration
col1.header(f"Well: {selected_well}")
total_days = 0
for process in processes[1:]:
    start_key, end_key = f"start_{process}", f"end_{process}"
    start, end = st.session_state[start_key], st.session_state[end_key]
    if start and end:
        duration = (end - start).days
        col1.write(f"{process}: {duration} days")
        total_days += duration
    else:
        col1.write(f"{process}: Add dates")

# Donut chart - Remaining Days
c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, 'On stream'))
on_stream_end = c.fetchone()

c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, 'Rig Release'))
rig_release_end = c.fetchone()

if on_stream_end and on_stream_end[0]:
    remaining = 0
    donut_label = "HU Completed, On Stream"
else:
    if rig_release_end and rig_release_end[0]:
        rig_date = pd.to_datetime(rig_release_end[0]).date()
        today = date.today()
        remaining = max(120 - (today - rig_date).days, 0)
        donut_label = f"{remaining} days remaining"
    else:
        remaining = 120
        donut_label = "Rig Release Missing"

fig_donut = px.pie(values=[remaining, 120 - remaining], names=[donut_label, "Completed"], hole=0.5)
fig_donut.update_traces(textinfo='none')
fig_donut.update_layout(showlegend=True, annotations=[dict(text=donut_label, x=0.5, y=0.5, font_size=14, showarrow=False)])
col1.plotly_chart(fig_donut)

# Column 2: KPI Comparison
col2.header("KPI Visualization and Comparison")
chart_data, progress_day_data = [], []

for well in wells:
    for process in processes[1:]:
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, process))
        res = c.fetchone()
        if res and res[0] and res[1]:
            duration = (pd.to_datetime(res[1]) - pd.to_datetime(res[0])).days
            chart_data.append({'Well': well, 'Process': process, 'Duration': duration})

    # Progress Days Table
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    on_stream = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig_release = c.fetchone()

    if on_stream and on_stream[0]:
        progress_day_data.append({'Well': well, 'Completion Progress Days': "HU Completed, On Stream"})
    elif rig_release and rig_release[0]:
        days = max(120 - (date.today() - pd.to_datetime(rig_release[0]).date()).days, 0)
        progress_day_data.append({'Well': well, 'Completion Progress Days': days})
    else:
        progress_day_data.append({'Well': well, 'Completion Progress Days': "No Rig Release"})

chart_df = pd.DataFrame(chart_data)
if not chart_df.empty:
    fig = px.bar(chart_df, x='Process', y='Duration', color='Well', barmode='group')
    col2.plotly_chart(fig)

# Completion Progress Days Table
progress_days_df = pd.DataFrame(progress_day_data)

def color_code(val):
    if isinstance(val, int):
        if val < 60:
            return 'background-color: orange'
        elif 60 <= val < 120:
            return 'background-color: green'
        else:
            return 'background-color: red'
    return ''

col2.dataframe(progress_days_df.style.applymap(color_code), use_container_width=True)

# Column 3: Completion Percentage
col3.header("Progress Overview & Gap Analysis")
progress_summary = []
for well in wells:
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig_release = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    on_stream = c.fetchone()

    if rig_release and rig_release[0] and on_stream and on_stream[0]:
        total = (pd.to_datetime(on_stream[0]) - pd.to_datetime(rig_release[0])).days
        percent = round((total / 120) * 100, 1)
        progress_summary.append({"Well": well, "Total Days": total, "Completion Percentage": f"{percent}%"})
    else:
        progress_summary.append({"Well": well, "Total Days": None, "Completion Percentage": None})

progress_df = pd.DataFrame(progress_summary)
col3.dataframe(progress_df, use_container_width=True)

col3.write("### Gap Analysis")
for row in progress_summary:
    if row['Total Days'] is not None:
        delta = row['Total Days'] - 120
        status = "Over" if delta > 0 else "Under"
        col3.write(f"{row['Well']}: {status} target by {abs(delta)} days")
    else:
        col3.write(f"{row['Well']}: Missing Rig Release or On Stream date")
