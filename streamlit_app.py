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
    initial_sidebar_state="expanded"
)

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

# Well and process list
wells = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliet"]

kpi_values = {
    "WLCTF_ UWO ➔ GGO": 15,
    "Standalone Activity": 15,
    "On Plot Hookup": 35,
    "Pre-commissioning": 8,
    "Unhook": 10,
    "WLCTF_GGO ➔ UWIF": 5,
    "Waiting IFS Resources": 20,
    "Frac Execution": 14,
    "WLCTF_UWIF ➔ GGO": 5,
    "Re-Hook & commissioning": 8,
    "Plug Removal": 15,
    "On stream": 1
}

processes = ["Rig Release"] + list(kpi_values.keys())

# Sidebar - Well Selection
st.sidebar.header("Well Selection and Data Entry")
selected_well = st.sidebar.selectbox("Select a Well", wells)

# Load session state with existing values
for process in processes:
    key_start = f"start_{process}"
    key_end = f"end_{process}"
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
    result = c.fetchone()
    st.session_state[key_start] = pd.to_datetime(result[0]).date() if result and result[0] else None
    st.session_state[key_end] = pd.to_datetime(result[1]).date() if result and result[1] else None

# Data Entry Interface
if role == "entry":
    # Rig Release Input
    rig_key = "end_Rig Release"
    rig_default = st.session_state.get(rig_key, date.today())
    rig_date = st.sidebar.date_input("Rig Release", value=rig_default, key="rig_release")

    if rig_date:
        c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                  (selected_well, "Rig Release", rig_date.isoformat(), rig_date.isoformat()))
        conn.commit()
        st.session_state[rig_key] = rig_date

    for process in processes[1:]:
        st.sidebar.markdown(f"**{process}**")
        col_start, col_end = st.sidebar.columns(2)

        key_start = f"start_{process}"
        key_end = f"end_{process}"

        with col_start:
            default_start = st.session_state[key_start] or date.today()
            start_date = st.date_input(f"Start - {process}", value=default_start, key=key_start)

        with col_end:
            default_end = st.session_state[key_end] or date.today()
            end_date = st.date_input(f"End - {process}", value=default_end, key=key_end)

        if start_date and end_date and start_date > end_date:
            st.sidebar.error(f"Start must be before End for {process}")
        elif start_date and end_date:
            c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                      (selected_well, process, start_date.isoformat(), end_date.isoformat()))
            conn.commit()

# Layout Columns
col1, col2, col3 = st.columns((1.5, 4.5, 2), gap="medium")

# === Column 1: Well Progress ===
col1.header(f"Well: {selected_well}")
total_days = 0

for process in processes[1:]:
    s_key, e_key = f"start_{process}", f"end_{process}"
    s_date, e_date = st.session_state[s_key], st.session_state[e_key]
    kpi = kpi_values.get(process)

    if s_date and e_date:
        duration = (e_date - s_date).days
        total_days += duration
        status = "✅ On Track" if duration <= kpi else "⚠️ Delayed"
        col1.write(f"{process}: {duration} days | KPI: {kpi} | {status}")
    else:
        col1.write(f"{process}: Add dates")

# Donut chart for remaining days
c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, 'Rig Release'))
rig = c.fetchone()
c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, 'On stream'))
ons = c.fetchone()

if ons and ons[0]:
    rem_days = 0
    donut_label = "HU Completed"
else:
    if rig and rig[0]:
        elapsed = (date.today() - pd.to_datetime(rig[0]).date()).days
        rem_days = max(120 - elapsed, 0)
        donut_label = f"{rem_days} Days Remaining"
    else:
        rem_days = 120
        donut_label = "No Rig Release"

fig_donut = px.pie(values=[rem_days, 120 - rem_days], names=["Remaining", "Elapsed"], hole=0.6)
fig_donut.update_traces(textinfo="none")
fig_donut.update_layout(annotations=[dict(text=donut_label, x=0.5, y=0.5, font_size=16, showarrow=False)])
col1.plotly_chart(fig_donut)

# === Column 2: KPI Comparison Chart ===
col2.header("KPI Visualization and Comparison")
chart_data = []
progress_data = []

for well in wells:
    for process in processes[1:]:
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, process))
        res = c.fetchone()
        if res and res[0] and res[1]:
            duration = (pd.to_datetime(res[1]) - pd.to_datetime(res[0])).days
            chart_data.append({"Well": well, "Process": process, "Duration": duration})

    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, "Rig Release"))
    rig = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, "On stream"))
    ons = c.fetchone()

    if ons and ons[0]:
        progress_data.append({"Well": well, "Completion Progress Days": "HU Completed"})
    elif rig and rig[0]:
        days_left = max(120 - (date.today() - pd.to_datetime(rig[0]).date()).days, 0)
        progress_data.append({"Well": well, "Completion Progress Days": days_left})
    else:
        progress_data.append({"Well": well, "Completion Progress Days": "No Rig Release"})

if chart_data:
    df = pd.DataFrame(chart_data)
    fig = px.bar(df, x="Process", y="Duration", color="Well", barmode="group")
    col2.plotly_chart(fig)

def highlight(val):
    if isinstance(val, int):
        if val < 60:
            return "background-color: red"
        elif 60 <= val < 120:
            return "background-color: orange"
        else:
            return "background-color: green"
    return ""

col2.dataframe(pd.DataFrame(progress_data).style.applymap(highlight), use_container_width=True)

# === Column 3: Gap & Completion ===
col3.header("Progress Overview & Gap Analysis")
summary = []

for well in wells:
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, "Rig Release"))
    rig = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, "On stream"))
    ons = c.fetchone()

    if rig and rig[0] and ons and ons[0]:
        total = (pd.to_datetime(ons[0]) - pd.to_datetime(rig[0])).days
        percent = round((total / 120) * 100, 1)
        summary.append({"Well": well, "Total Days": total, "Completion %": f"{percent}%"})
    else:
        summary.append({"Well": well, "Total Days": None, "Completion %": None})

col3.dataframe(pd.DataFrame(summary), use_container_width=True)

col3.write("### Gap Analysis")
for row in summary:
    if row["Total Days"] is not None:
        gap = row["Total Days"] - 120
        status = "Over" if gap > 0 else "Under"
        col3.write(f"{row['Well']}: {status} target by {abs(gap)} days")
    else:
        col3.write(f"{row['Well']}: Missing dates")
