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
processes = ["Rig Release",
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
    "On stream"]

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
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
        result = c.fetchone()
        st.session_state[key_start] = pd.to_datetime(result[0]).date() if result and result[0] else None
        st.session_state[key_end] = pd.to_datetime(result[1]).date() if result and result[1] else None

if role == "entry":
    st.sidebar.markdown("---")
    st.sidebar.subheader("Date Entry")

    for proc in processes:
        st.sidebar.markdown(f"**{proc}**")
        skey, ekey = f"start_{proc}", f"end_{proc}"
        cs, ce, clr = st.sidebar.columns([2, 2, 1])

        with cs:
            sd = st.date_input(f"Start - {proc}", value=st.session_state.get(skey), key=skey)
        with ce:
            ed = st.date_input(f"End - {proc}", value=st.session_state.get(ekey), key=ekey)
        with clr:
            if st.button("🗑️", key=f"clear_{proc}"):
                c.execute("DELETE FROM process_data WHERE well=? AND process=?", (selected_well, proc))
                conn.commit()
                st.session_state[skey] = None
                st.session_state[ekey] = None
                st.experimental_rerun()

        if sd and ed:
            if sd > ed:
                st.sidebar.error(f"Start date > End date for {proc}")
            else:
                c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                          (selected_well, proc, sd.isoformat(), ed.isoformat()))
                conn.commit()

# Visualization columns
col1, col2, col3 = st.columns((1.5, 4.5, 2), gap='medium')

# Column 1: Process durations
col1.header(f"Well: {selected_well}")
for process in processes[1:]:
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
    result = c.fetchone()
    if result and result[0] and result[1]:
        duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
        col1.write(f"{process}: {duration} days")
    else:
        col1.write(f"{process}: Add dates")

# Donut chart: Remaining Days
c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, 'Rig Release'))
rig_release = c.fetchone()
c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, 'On stream'))
on_stream = c.fetchone()
remaining_days = None
label = ""

if rig_release and rig_release[0]:
    rig_date = pd.to_datetime(rig_release[0]).date()
    if on_stream and on_stream[0]:
        label = "HU Completed, On Stream"
        remaining_days = 0
    else:
        today = date.today()
        remaining_days = 120 - (today - rig_date).days
        label = f"{remaining_days} days"

if remaining_days is not None:
    donut_df = pd.DataFrame({
        'Status': ['Remaining', 'Completed'],
        'Days': [max(remaining_days, 0), 120 - max(remaining_days, 0)]
    })
    fig_donut = px.pie(donut_df, values='Days', names='Status', hole=0.5)
    fig_donut.update_traces(textinfo='label+percent', textposition='inside')
    fig_donut.update_layout(annotations=[dict(text=label, x=0.5, y=0.5, font_size=16, showarrow=False)])
    col1.plotly_chart(fig_donut)

# Column 2: KPI bar chart
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

# Column 2: Completion Progress Days table
progress_days_data = []
today = date.today()
for well in wells:
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    stream = c.fetchone()
    if rig and rig[0]:
        rig_date = pd.to_datetime(rig[0]).date()
        if stream and stream[0]:
            val = "HU Completed, On Stream"
        else:
            val = 120 - (today - rig_date).days
        progress_days_data.append({'Well': well, 'Completion Progress Days': val})

col2.subheader("Completion Progress Days")
pdf = pd.DataFrame(progress_days_data)

def color_code(val):
    if isinstance(val, int):
        if val <= 0:
            return 'background-color: red'
        elif val < 60:
            return 'background-color: orange'
        elif val <= 120:
            return 'background-color: green'
        else:
            return 'background-color: red'
    return ''

col2.dataframe(pdf.style.applymap(color_code, subset=['Completion Progress Days']), use_container_width=True)

# Column 3: Progress Overview & Gap Analysis
col3.header("Progress Overview & Gap Analysis")
progress_data = []
gap_analysis = []
for well in wells:
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    stream = c.fetchone()
    if rig and rig[0] and stream and stream[0]:
        total_days = max((pd.to_datetime(stream[0]) - pd.to_datetime(rig[0])).days, 1)
        completion_pct = round((total_days / 120) * 100, 1)
        progress_data.append({"Well": well, "Total Days": total_days, "Completion Percentage": f"{completion_pct}%"})
        gap = total_days - 120
        gap_analysis.append(f"{well}: {'Over' if gap > 0 else 'Under'} target by {abs(gap)} days")
    else:
        progress_data.append({"Well": well, "Total Days": None, "Completion Percentage": None})
        gap_analysis.append(f"{well}: Missing Rig Release or On stream dates")

pdf3 = pd.DataFrame(progress_data)
col3.dataframe(pdf3, use_container_width=True)
col3.subheader("Gap Analysis")
for gap in gap_analysis:
    col3.write(gap)
