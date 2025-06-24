##This is our EE project##

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
    "MU63638001": "entry",
    "MU64275002": "entry",
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
processes = ["Rig Release",
    "WLCTF_ UWO ➔ GGO",
    "Standalone Activity",
    "On Plot Hookup",
    "Pre-commissioning",
    "Unhook",
    "WLCTF_GGO ➔ UWIF",
    "Waiting IFS Resources",
    "Frac Execution", "WLCTF_UWIF ➔ GGO",
    "Re-Hook & commissioning",
    "Plug Removal",
    "On stream"]

# Define KPI targets for each process
kpi_targets = {
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

# Layout
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
        st.session_state[key_start] = pd.to_datetime(result[0]).date() if result and result[0] else None
        st.session_state[key_end] = pd.to_datetime(result[1]).date() if result and result[1] else None

if role == "entry":
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "Rig Release"))
    saved_rig = c.fetchone()
    rig_release_key = "rig_release"
    default_rig_release = pd.to_datetime(saved_rig[0]).date() if saved_rig and saved_rig[0] else None

    if saved_rig and saved_rig[0]:
        rig_release_date = st.sidebar.date_input("Rig Release", value=default_rig_release, key=rig_release_key, help="Rig Release already recorded for this well")
    else:
        rig_release_date = st.sidebar.date_input("Rig Release", key=rig_release_key)

    if rig_release_date and not saved_rig:
        c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                  (selected_well, "Rig Release", rig_release_date.isoformat(), rig_release_date.isoformat()))
        conn.commit()
        st.session_state[f"end_Rig Release"] = rig_release_date

    for process in processes[1:]:
        st.sidebar.markdown(f"**{process}**")
        col_start, col_end = st.sidebar.columns(2)
        key_start = f"start_{process}"
        key_end = f"end_{process}"

        with col_start:
            default_start = st.session_state.get(key_start)
            start_date = st.date_input(f"Start - {process}", value=default_start, key=key_start)

        with col_end:
            default_end = st.session_state.get(key_end)
            end_date = st.date_input(f"End - {process}", value=default_end, key=key_end)

        if start_date and end_date and start_date > end_date:
            st.sidebar.error(f"Error: Start date must be before or equal to End date for {process}")
        elif start_date and end_date:
            c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                      (selected_well, process, start_date.isoformat(), end_date.isoformat()))
            conn.commit()

col1, col2, col3 = st.columns((1.5, 4.5, 2), gap='medium')

col1.header(f"Well: {selected_well}")
total_duration = 0
for process in processes[1:]:
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
    result = c.fetchone()
    if result and result[0] and result[1]:
        duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
        total_duration += duration
        kpi = kpi_targets.get(process, None)
        status = "✅ On Track" if kpi and duration <= kpi else ("⚠️ Delayed" if kpi else "N/A")
        col1.write(f"{process}: {duration} days (KPI: {kpi}) {status}")
    else:
        col1.write(f"{process}: Add dates")

c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "Rig Release"))
rig = c.fetchone()
c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "On stream"))
onstream = c.fetchone()

if onstream and onstream[0]:
    remaining = 0
    label = "HU Completed, On Stream"
else:
    if rig and rig[0]:
        delta = (date.today() - pd.to_datetime(rig[0]).date()).days
        remaining = 120 - delta
        label = f"{remaining} days"
    else:
        remaining = 120
        label = "No Rig Date"

fig_donut = px.pie(values=[remaining, 120 - remaining], names=['Remaining', 'Elapsed'], hole=0.6)
fig_donut.update_traces(textinfo='none')
fig_donut.add_annotation(text=label, x=0.5, y=0.5, font_size=18, showarrow=False)
col1.plotly_chart(fig_donut)

conn.close()
