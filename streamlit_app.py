import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime
import plotly.express as px
import altair as alt

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
    "viewer1": "view",
    "viewer2": "view"
}

username = st.sidebar.text_input("Username")
if username not in USERS:
    st.sidebar.error("User not recognized")
    st.stop()
role = USERS[username]

wells = ["SNN-11", "SN-113", "SN-114", "SNN-10", "SR-603", "SN-115", "BRNW-106", "SNNORTH11_DEV", "SRM-V36A", "SRM-VE127"]
processes = [
    "Rig Release",
    "WLCTF_ UWO ➜ GGO", "Standalone Activity", "On Plot Hookup", "Pre-commissioning", "Unhook",
    "WLCTF_GGO ➜ UWIF", "Waiting IFS Resources", "Frac Execution",
    "Re-Hook & commissioning", "Plug Removal", "On stream"
]

# Sidebar well selection
st.sidebar.header("Well Selection and Data Entry")
previous_well = st.session_state.get('selected_well', None)
selected_well = st.sidebar.selectbox("Select a Well", wells)
st.session_state['selected_well'] = selected_well

# Clear or populate inputs on well change
if previous_well != selected_well:
    for process in processes:
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
        result = c.fetchone()
        st.session_state[f"start_{process}"] = pd.to_datetime(result[0]).date() if result and result[0] else None
        st.session_state[f"end_{process}"] = pd.to_datetime(result[1]).date() if result and result[1] else None

if role == "entry":
    # Rig Release logic
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "Rig Release"))
    saved_rig_release = c.fetchone()
    rig_release_key = "rig_release"
    rig_release_val = pd.to_datetime(saved_rig_release[0]).date() if saved_rig_release else None

    rig_release_date = st.sidebar.date_input("Rig Release", value=rig_release_val, key=rig_release_key)
    if rig_release_date and (not saved_rig_release or rig_release_date != rig_release_val):
        c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                  (selected_well, "Rig Release", rig_release_date.isoformat(), rig_release_date.isoformat()))
        conn.commit()

    # Other processes
    for process in processes[1:]:
        key_start = f"start_{process}"
        key_end = f"end_{process}"
        st.sidebar.markdown(f"**{process}**")
        col_start, col_end = st.sidebar.columns(2)

        with col_start:
            default_start = st.session_state.get(key_start)
            start_date = st.date_input(f"Start - {process}", value=default_start, key=key_start)
        with col_end:
            default_end = st.session_state.get(key_end)
            end_date = st.date_input(f"End - {process}", value=default_end, key=key_end)

        if start_date and end_date and start_date <= end_date:
            c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                      (selected_well, process, start_date.isoformat(), end_date.isoformat()))
            conn.commit()

# Layout columns
col1, col2, col3 = st.columns((1.5, 4.5, 2), gap='medium')

# Column 1: Well Process Durations
col1.header(f"Well: {selected_well}")
for process in processes[1:]:
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
    result = c.fetchone()
    if result and result[0] and result[1]:
        duration = (pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days
        col1.write(f"{process}: {duration} days")
    else:
        col1.write(f"{process}: Add dates")

# Donut Chart for Remaining Days
c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "Rig Release"))
rig_release = c.fetchone()
c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "On stream"))
on_stream = c.fetchone()

if rig_release and rig_release[0]:
    rig_date = pd.to_datetime(rig_release[0]).date()
    if on_stream and on_stream[0]:
        remaining_days = 0
        label = "HU Completed, On Stream"
    else:
        remaining_days = 120 - (date.today() - rig_date).days
        label = f"{remaining_days} days"

    color = "green" if remaining_days < 60 else "orange" if remaining_days < 120 else "red"
    fig_donut = px.pie(
        names=["Remaining", "Elapsed"],
        values=[max(remaining_days, 0), 120 - max(remaining_days, 0)],
        hole=0.6,
        color_discrete_sequence=[color, "#d3d3d3"]
    )
    fig_donut.update_traces(textinfo="none", hoverinfo='label+percent')
    fig_donut.update_layout(
        annotations=[dict(text=label, x=0.5, y=0.5, font_size=20, showarrow=False)],
        showlegend=False,
        margin=dict(t=10, b=10, l=10, r=10)
    )
    col1.plotly_chart(fig_donut)

# Column 2: Bar Chart & Completion Table
col2.header("KPI Visualization and Comparison")

chart_data = []
completion_row = {"Well": [], "Completion Progress Days": []}
for well in wells:
    for process in processes[1:]:
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, process))
        result = c.fetchone()
        if result and result[0] and result[1]:
            days = (pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days
            chart_data.append({'Well': well, 'Process': process, 'Duration': days})

    # Completion Days
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, "Rig Release"))
    rig = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, "On stream"))
    on_stream = c.fetchone()
    if rig and rig[0]:
        rig_date = pd.to_datetime(rig[0]).date()
        if on_stream and on_stream[0]:
            completion = "HU Completed, On Stream"
        else:
            completion = 120 - (date.today() - rig_date).days
    else:
        completion = None

    completion_row["Well"].append(well)
    completion_row["Completion Progress Days"].append(completion)

chart_df = pd.DataFrame(chart_data)
if not chart_df.empty:
    fig = px.bar(chart_df, x='Process', y='Duration', color='Well', barmode='group')
    col2.plotly_chart(fig)

# Add Completion Table
completion_df = pd.DataFrame(completion_row).set_index("Well")

def highlight_days(val):
    if isinstance(val, int):
        if val > 120:
            return 'background-color: red; color: white'
        elif val > 60:
            return 'background-color: orange'
        else:
            return 'background-color: lightgreen'
    return ''

col2.dataframe(completion_df.style.applymap(highlight_days), use_container_width=True)

# Column 3: Progress Overview
col3.header("Progress Overview & Gap Analysis")

progress_data = []
gap_analysis = []

for well in wells:
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig_release = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    on_stream = c.fetchone()
    if rig_release and rig_release[0] and on_stream and on_stream[0]:
        total_days = (pd.to_datetime(on_stream[0]) - pd.to_datetime(rig_release[0])).days
        completion_percent = round((total_days / 120) * 100, 1)
        color = "#32CD32" if total_days <= 120 else "#FF6347"
        progress_data.append({"Well": well, "Total Days": total_days, "Completion Percentage": f"{completion_percent}%", "Color": color})
        gap_analysis.append(f"{well}: {'Over' if total_days > 120 else 'Under'} target by {abs(total_days - 120)} days")
    else:
        progress_data.append({"Well": well, "Total Days": None, "Completion Percentage": None, "Color": None})
        gap_analysis.append(f"{well}: Missing Rig Release or On stream dates")

progress_df = pd.DataFrame(progress_data)

if not progress_df.empty:
    styled_df = progress_df.drop(columns=["Color"]).style.apply(
        lambda x: [f"background-color: {progress_df.loc[x.name, 'Color']}" if progress_df.loc[x.name, 'Color'] else "" for _ in x],
        axis=1
    )
    col3.dataframe(styled_df, use_container_width=True)

col3.write("### Gap Analysis")
for gap in gap_analysis:
    col3.write(gap)
