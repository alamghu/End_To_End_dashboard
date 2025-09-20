import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime
import plotly.express as px
import plotly.graph_objects as go
import calendar

st.set_page_config(
    page_title="End To End Tracking Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded")


# Database setup
DB_PATH = 'tracking_data.db'
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# Create tables if not exist
c.execute('''CREATE TABLE IF NOT EXISTS process_data (
    well TEXT,
    process TEXT,
    start_date TEXT,
    end_date TEXT,
    PRIMARY KEY (well, process)
)''')

c.execute('''CREATE TABLE IF NOT EXISTS workflow_type (
    well TEXT PRIMARY KEY,
    workflow TEXT
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

# KPI process
kpi_dict = {
    "Rig Release": 4,
    "WLCTF_ UWO ➔ GGO": 15,
    "Standalone Activity": 5,
    "On Plot Hookup": 35,
    "Pre-commissioning": 7,
    "Unhook": 8,
    "WLCTF_GGO ➔ UWIF": 0,
    "Waiting IFS Resources": 14,
    "Frac Execution": 26,
    "Re-Hook & commissioning": 8,
    "Plug Removal": 1,
    "On stream": 1
} 

# Layout
st.sidebar.header("Well Selection and Data Entry")
previous_well = st.session_state.get('selected_well', None)
selected_well = st.sidebar.selectbox("Select a Well", wells)
st.session_state['selected_well'] = selected_well

# Load saved workflow from DB
c.execute('SELECT workflow FROM workflow_type WHERE well = ?', (selected_well,))
saved_workflow = c.fetchone()
default_workflow = saved_workflow[0] if saved_workflow else "HBF"

# Workflow dropdown (HBF / HAF)
selected_workflow = st.sidebar.selectbox("Select Workflow", ["HBF", "HAF"], index=["HBF", "HAF"].index(default_workflow))
st.session_state["workflow_type"] = selected_workflow

# Update workflow in DB if changed
if saved_workflow is None or selected_workflow != saved_workflow[0]:
    c.execute('REPLACE INTO workflow_type (well, workflow) VALUES (?, ?)', (selected_well, selected_workflow))
    conn.commit()

# Restore dates from DB when changing well
if previous_well != selected_well:
    for process in processes:
        key_start = f"start_{process}"
        key_end = f"end_{process}"
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
        result = c.fetchone()
        st.session_state[key_start] = pd.to_datetime(result[0]).date() if result and result[0] else None
        st.session_state[key_end] = pd.to_datetime(result[1]).date() if result and result[1] else None

if role == "entry":
    # Rig Release
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "Rig Release"))
    saved_rig = c.fetchone()
    rig_release_key = "rig_release"
    default_rig_release = pd.to_datetime(saved_rig[0]).date() if saved_rig and saved_rig[0] else None

    rig_release_date = st.sidebar.date_input(
        "Rig Release",
        value=default_rig_release,
        key=rig_release_key,
        help="Enter Rig Release Date") if default_rig_release else st.sidebar.date_input("Rig Release", key=rig_release_key)

    if rig_release_date:
        c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                  (selected_well, "Rig Release", rig_release_date.isoformat(), rig_release_date.isoformat()))
        conn.commit()
        st.session_state[f"end_Rig Release"] = rig_release_date

    # Rig Out
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "Rig Out"))
    saved_rigout = c.fetchone()
    rig_out_key = "rig_out"
    default_rig_out = pd.to_datetime(saved_rigout[0]).date() if saved_rigout and saved_rigout[0] else None

    rig_out_date = st.sidebar.date_input(
        "Rig Out",
        value=default_rig_out,
        key=rig_out_key,
        help="Enter Rig Out Date") if default_rig_out else st.sidebar.date_input("Rig Out", key=rig_out_key)

    if rig_out_date:
        c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                  (selected_well, "Rig Out", rig_out_date.isoformat(), rig_out_date.isoformat()))
        conn.commit()
        st.session_state[f"end_Rig Out"] = rig_out_date

    # Remaining processes (except Rig Release)
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

# Layout columns
col1, col2, col3 = st.columns((1.5, 7.5, 1.5), gap='medium')

# Column 1: Well name + workflow
col1.header(f"Well: {selected_well} ({st.session_state['workflow_type']})")
total_duration = 0
for process in processes[1:]:
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
    result = c.fetchone()
    if result and result[0] and result[1]:
        duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
        total_duration += duration
        col1.write(f"{process}: {duration} days (KPI: {kpi_dict.get(process, '-')})")
    else:
        col1.write(f"{process}: Add dates (KPI: {kpi_dict.get(process, '-')})")

# Donut Chart in col1
# Get all processes and their dates for the selected well
c.execute('SELECT process, start_date, end_date FROM process_data WHERE well = ?', (selected_well,))
rows = c.fetchall()
df = pd.DataFrame(rows, columns=['process', 'start_date', 'end_date'])
df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce')
df['end_date'] = pd.to_datetime(df['end_date'], errors='coerce')

# Identify the ongoing process
ongoing_process = None
in_progress = df[(df['start_date'].notna()) & (df['end_date'].isna())]
if not in_progress.empty:
    ongoing_process = in_progress.iloc[0]['process']
else:
    completed = df[df['end_date'].notna()].sort_values(by='end_date')
    if not completed.empty:
        last_completed = completed.iloc[-1]['process']
        all_processes = df['process'].tolist()
        try:
            idx = all_processes.index(last_completed)
            ongoing_process = all_processes[idx + 1] if idx + 1 < len(all_processes) else last_completed
        except:
            ongoing_process = last_completed

# 2nd Donut Chart in col1 (120-day window) - UPDATED with traffic lights
progress_data = []

for well in wells:
    # Get current process (latest process with end_date)
    c.execute('SELECT process, start_date, end_date FROM process_data WHERE well = ? ORDER BY end_date DESC LIMIT 1', (well,))
    proc = c.fetchone()
    if proc:
        process_name, start, end = proc
        start_dt = pd.to_datetime(start) if start else None
        end_dt = pd.to_datetime(end) if end else None

        # Total days on current process (if both start and end exist)
        total_days = (end_dt - start_dt).days if start_dt is not None and end_dt is not None else None

        # Remaining days against KPI (of current process)
        remaining_days = 120 - total_days if total_days is not None else None

        # Completion color (traffic light)
        if total_days is not None:
            if total_days <= 90:
                row_color = '#32CD32'  # Green
            elif total_days <= 120:
                row_color = '#FFD700'  # Yellow
            else:
                row_color = '#FF6347'  # Red
        else:
            row_color = '#D3D3D3'  # Grey if missing

        # Gap / Status
        if remaining_days is not None:
            if remaining_days < 0:
                gap_text = f"Over target by {abs(remaining_days)} days"
            elif remaining_days == 0:
                gap_text = "On target"
            else:
                gap_text = f"Under target by {remaining_days} days"
        else:
            gap_text = "Missing data"

        progress_data.append({
            "Well": well,
            "Current Process": process_name,
            "Total days on Current Process": total_days,
            "Remaining Days": remaining_days,
            "Row Color": row_color,
            "Gap/Status": gap_text
        })
    else:
        progress_data.append({
            "Well": well,
            "Current Process": None,
            "Total days on Current Process": None,
            "Remaining Days": None,
            "Row Color": '#D3D3D3',
            "Gap/Status": "Missing data"
        })

progress_df = pd.DataFrame(progress_data)

# Highlight function for Remaining Days cell
def highlight_remaining(val):
    if isinstance(val,(int,float)):
        if val <= 0:
            return 'background-color: red; color:white'
        elif val <= 60:
            return 'background-color: orange'
        else:
            return 'background-color: green'
    return ''

col2.header("Well Progress Dashboard")
col2.markdown("""
**Legend:**  
- **Row Color:** green = within KPI, yellow = near KPI, red = exceeded KPI  
- **Remaining Days Cell:** green > 60, orange 0–60, red ≤ 0
""")

if not progress_df.empty:
    styled_df = progress_df.drop(columns=["Row Color"]).style.apply(
        lambda x: [f'background-color: {progress_df.loc[x.name, "Row Color"]}' for _ in x], axis=1
    ).applymap(highlight_remaining, subset=['Remaining Days'])
    col2.dataframe(styled_df, use_container_width=True)
else:
    col2.write("No progress data available.")

       


# Column 3: Completion Percentage and Gap Analysis
col3.header("Progress Overview & Gap Analysis")
progress_data_col3 = []
gap_analysis = []

for well in wells:
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    ons = c.fetchone()
    if rig and rig[0] and ons and ons[0]:
        total_days = max((pd.to_datetime(ons[0]) - pd.to_datetime(rig[0])).days, 1)
        progress = round((total_days / 120) * 100, 1)
        color = '#32CD32' if total_days <= 120 else '#FF6347'
        progress_data_col3.append({"Well": well, "Total Days": total_days, "Completion Percentage": f"{progress}%", "Color": color})
        gap = total_days - 120
        gap_analysis.append(f"{well}: {'Over' if gap > 0 else 'Under'} target by {abs(gap)} days")
    else:
        progress_data_col3.append({"Well": well, "Total Days": None, "Completion Percentage": None, "Color": None})
        gap_analysis.append(f"{well}: Missing Rig Release or On stream dates")

progress_df_col3 = pd.DataFrame(progress_data_col3)

if not progress_df_col3.empty:
    def color_cells(val, color):
        return f'background-color: {color}' if color else ''

    styled_df_col3 = progress_df_col3.drop(columns=["Color"]).style.apply(
        lambda x: [color_cells(v, progress_df_col3.loc[x.name, "Color"]) for v in x], axis=1)
    col3.dataframe(styled_df_col3, use_container_width=True)
else:
    col3.write("No completion data available.")

col3.write("### Gap Analysis")
for gap in gap_analysis:
    col3.write(gap)
