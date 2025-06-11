import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime
import altair as alt
import plotly.express as px
import matplotlib.pyplot as plt

st.set_page_config(
    page_title="End To End Tracking Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded")

alt.themes.enable("dark")

# DB Setup
DB_PATH = 'tracking_data.db'
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS process_data (
    well TEXT,
    process TEXT,
    start_date TEXT,
    end_date TEXT,
    PRIMARY KEY (well, process)
)''')
conn.commit()

USERS = {
    "user1": "entry",
    "user2": "entry",
    "viewer1": "view"
}

username = st.sidebar.text_input("Username")
if username not in USERS:
    st.sidebar.error("User not recognized")
    st.stop()
role = USERS[username]

wells = ["SNN-11", "SN-113", "SN-114", "SNN-10", "SR-603", "SN-115", "BRNW-106", "SNNORTH11_DEV", "SRM-V36A", "SRM-VE127"]
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

st.sidebar.header("Well Selection and Data Entry")
previous_well = st.session_state.get('selected_well', None)
selected_well = st.sidebar.selectbox("Select a Well", wells)
st.session_state['selected_well'] = selected_well

if previous_well != selected_well:
    for process in processes:
        key_start = f"start_{process}"
        key_end = f"end_{process}"
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
        result = c.fetchone()
        if result:
            st.session_state[key_start] = pd.to_datetime(result[0]).date() if result[0] else None
            st.session_state[key_end] = pd.to_datetime(result[1]).date() if result[1] else None
        else:
            st.session_state[key_start] = None
            st.session_state[key_end] = None

if role == "entry":
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?',(selected_well, "Rig Release"))
    rig_result = c.fetchone()
    rig_release_date = pd.to_datetime(rig_result[0]).date() if rig_result and rig_result[0] else None

    rig_release_input = st.sidebar.date_input("Rig Release", value=rig_release_date if rig_release_date else None, key="rig_release")
    if rig_release_input:
        c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                  (selected_well, "Rig Release", rig_release_input.isoformat(), rig_release_input.isoformat()))
        conn.commit()
        st.session_state[f"end_Rig Release"] = rig_release_input

    for process in processes[1:]:
        key_start = f"start_{process}"
        key_end = f"end_{process}"
        st.sidebar.markdown(f"**{process}**")
        col_start, col_end = st.sidebar.columns(2)

        with col_start:
            default_start = st.session_state.get(key_start, None)
            start_date = st.date_input(f"Start - {process}", value=default_start, key=key_start)

        with col_end:
            default_end = st.session_state.get(key_end, None)
            end_date = st.date_input(f"End - {process}", value=default_end, key=key_end)

        if start_date and end_date and start_date > end_date:
            st.sidebar.error(f"Error: Start date must be before or equal to End date for {process}")
        elif start_date and end_date:
            c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                      (selected_well, process, start_date.isoformat(), end_date.isoformat()))
            conn.commit()

col1, col2, col3 = st.columns((1.5, 4.5, 2), gap='medium')

col1.header(f"Well: {selected_well}")

# Donut chart function
def donut_chart(remaining_days):
    days_done = 120 - remaining_days
    values = [days_done, remaining_days]
    color = '#00cc66' if remaining_days <= 60 else '#ffa500' if remaining_days < 120 else '#ff4d4d'
    fig, ax = plt.subplots(figsize=(3, 3))
    wedges, _ = ax.pie(values, startangle=90, colors=[color, '#e0e0e0'], wedgeprops=dict(width=0.3))
    ax.text(0, 0, f"{remaining_days} days", ha='center', va='center', fontsize=14)
    ax.set_aspect('equal')
    return fig

for process in processes[1:]:
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
    result = c.fetchone()
    if result and result[0] and result[1]:
        duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
        col1.write(f"{process}: {duration} days")
    else:
        col1.write(f"{process}: Add dates")

# Donut
c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, 'Rig Release'))
rig = c.fetchone()
c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, 'On stream'))
on_stream = c.fetchone()
remaining_days = None
if rig and rig[0]:
    if on_stream and on_stream[0]:
        label = "HU Completed, On Stream"
        remaining_days = 0
    else:
        delta = (120 - (date.today() - pd.to_datetime(rig[0]).date()).days)
        remaining_days = max(delta, 0)

    fig = donut_chart(remaining_days)
    col1.pyplot(fig)

# KPI and Completion Progress Days table
col2.header("KPI Visualization and Comparison")
chart_data, prog_days = [], []
for well in wells:
    for process in processes[1:]:
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, process))
        result = c.fetchone()
        if result and result[0] and result[1]:
            duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
            chart_data.append({'Well': well, 'Process': process, 'Duration': duration})

    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    stream = c.fetchone()

    if stream and stream[0]:
        prog_days.append("HU Completed, On Stream")
    elif rig and rig[0]:
        delta = 120 - (date.today() - pd.to_datetime(rig[0]).date()).days
        prog_days.append(max(delta, 0))
    else:
        prog_days.append("No Rig Release")

chart_df = pd.DataFrame(chart_data)
if not chart_df.empty:
    fig = px.bar(chart_df, x='Process', y='Duration', color='Well', barmode='group')
    col2.plotly_chart(fig)

col2.write("### Completion Progress Days")
progress_table = pd.DataFrame([prog_days], columns=wells, index=["Completion Progress Days"])

# Highlighting function
def highlight(val):
    if isinstance(val, (int, float)):
        if val < 60:
            return 'background-color: red; color: white'
        elif 60 <= val < 120:
            return 'background-color: orange; color: black'
        else:
            return 'background-color: green; color: white'
    return ''

col2.dataframe(progress_table.style.applymap(highlight), use_container_width=True)

# Column 3: Progress Overview
col3.header("Progress Overview & Gap Analysis")
progress_data = []
for well in wells:
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    stream = c.fetchone()
    if rig and rig[0] and stream and stream[0]:
        days = max((pd.to_datetime(stream[0]) - pd.to_datetime(rig[0])).days, 1)
        perc = round((days / 120) * 100, 1)
        progress_data.append({"Well": well, "Total Days": days, "Completion Percentage": f"{perc}%"})
    else:
        progress_data.append({"Well": well, "Total Days": None, "Completion Percentage": None})

col3.dataframe(pd.DataFrame(progress_data), use_container_width=True)

col3.write("### Gap Analysis")
for row in progress_data:
    if row['Total Days'] is None:
        col3.write(f"{row['Well']}: Missing Rig Release or On stream dates")
    else:
        diff = row['Total Days'] - 120
        if diff > 0:
            col3.write(f"{row['Well']}: Over target by {diff} days")
        else:
            col3.write(f"{row['Well']}: Under target by {-diff} days")
