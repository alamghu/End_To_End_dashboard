# Updated Streamlit app 11/06/2025 @ 8am

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
        if result:
            st.session_state[key_start] = pd.to_datetime(result[0]).date() if result[0] else None
            st.session_state[key_end] = pd.to_datetime(result[1]).date() if result[1] else None
        else:
            st.session_state[key_start] = None
            st.session_state[key_end] = None

if role == "entry":
    # Rig Release - Single Date Input (Only for selected well)
    rig_release_key = f"rig_release_{selected_well}"
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?',(selected_well, "Rig Release"))
    saved_rig_release = c.fetchone()
    default_rig_release = pd.to_datetime(saved_rig_release[0]).date() if saved_rig_release else None
    rig_release_date = st.sidebar.date_input("Rig Release", value=default_rig_release, key=rig_release_key)
    if rig_release_date:
        c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                  (selected_well, "Rig Release", rig_release_date.isoformat(), rig_release_date.isoformat()))
        conn.commit()
        st.session_state[f"end_Rig Release"] = rig_release_date

    # Process Data Entry for other processes
    for process in processes[1:]:
        key_start = f"start_{process}"
        key_end = f"end_{process}"
        st.sidebar.markdown(f"**{process}**")
        col_start, col_end = st.sidebar.columns(2)

        with col_start:
            start_date = st.date_input(f"Start - {process}", value=st.session_state.get(key_start), key=key_start)

        with col_end:
            end_date = st.date_input(f"End - {process}", value=st.session_state.get(key_end), key=key_end)

        if start_date and end_date and start_date > end_date:
            st.sidebar.error(f"Error: Start date must be before or equal to End date for {process}")
        elif start_date and end_date:
            c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                      (selected_well, process, start_date.isoformat(), end_date.isoformat()))
            conn.commit()

# Visualization columns
col1, col2, col3 = st.columns((1.5, 4.5, 2), gap='medium')

# --- Column 1: Well being updated ---
col1.header(f"Well: {selected_well}")
for process in processes[1:]:
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
    result = c.fetchone()
    if result and result[0] and result[1]:
        duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
        col1.write(f"{process}: {duration} days")
    else:
        col1.write(f"{process}: Add dates")

# --- Donut Chart in Column 1 ---
c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "Rig Release"))
rig = c.fetchone()
if rig and rig[0]:
    rig_date = pd.to_datetime(rig[0]).date()
    days_passed = (date.today() - rig_date).days
    remaining = 120 - days_passed
    donut_color = "green" if remaining < 60 else "orange" if remaining <= 120 else "red"
    donut_df = pd.DataFrame({"Label": ["Remaining", "Elapsed"], "Days": [max(remaining, 0), min(days_passed, 120)]})
    fig_donut = px.pie(donut_df, names='Label', values='Days', hole=0.6, color_discrete_sequence=[donut_color, "lightgray"])
    fig_donut.update_layout(
        annotations=[dict(text=f"{max(remaining, 0)}\ndays", x=0.5, y=0.5, font_size=18, showarrow=False)],
        showlegend=False
    )
    col1.plotly_chart(fig_donut, use_container_width=True)

# --- Column 2: KPI Visualization ---
col2.header("KPI Visualization and Comparison")
chart_data = []
progress_row = []

for well in wells:
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig = c.fetchone()
    if rig and rig[0]:
        rig_date = pd.to_datetime(rig[0]).date()
        days_passed = (date.today() - rig_date).days
        remaining = 120 - days_passed
        color = "green" if remaining < 60 else "orange" if remaining <= 120 else "red"
    else:
        remaining = None
        color = "gray"
    progress_row.append((well, remaining, color))
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

# Add Completion Progress Days table
if progress_row:
    wells_list, days_list, colors = zip(*progress_row)
    table_df = pd.DataFrame([days_list], columns=wells_list, index=["Completion Progress Days"])
    def color_cells(val):
        if val is None:
            return 'background-color: gray'
        elif val > 120:
            return 'background-color: red'
        elif val > 60:
            return 'background-color: orange'
        else:
            return 'background-color: green'
    styled = table_df.style.applymap(color_cells)
    col2.dataframe(styled, use_container_width=True)

# --- Column 3: Completion Percentage & Gap Analysis ---
col3.header("Progress Overview & Gap Analysis")
progress_data = []
gap_analysis = []
for well in wells:
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    on_stream = c.fetchone()
    if rig and rig[0] and on_stream and on_stream[0]:
        total_days = max((pd.to_datetime(on_stream[0]) - pd.to_datetime(rig[0])).days, 1)
        percentage = round((total_days / 120) * 100, 1)
        color = "green" if total_days <= 120 else "red"
        progress_data.append({"Well": well, "Total Days": total_days, "Completion Percentage": f"{percentage}%", "Color": color})
        gap = total_days - 120
        gap_analysis.append(f"{well}: {'Over' if gap > 0 else 'Under'} target by {abs(gap)} days")
    else:
        progress_data.append({"Well": well, "Total Days": None, "Completion Percentage": None, "Color": None})
        gap_analysis.append(f"{well}: Missing Rig Release or On stream dates")

progress_df = pd.DataFrame(progress_data)
if not progress_df.empty:
    def color_progress(val, color):
        return f'background-color: {color}' if color else ''
    display_df = progress_df.drop(columns=["Color"])
    styled_df = display_df.style.apply(lambda x: [color_progress(v, progress_df.loc[x.name, "Color"]) for v in x], axis=1)
    col3.dataframe(styled_df, use_container_width=True)

col3.write("### Gap Analysis")
for gap in gap_analysis:
    col3.write(gap)
