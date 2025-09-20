import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime
import plotly.express as px
import plotly.graph_objects as go

# ============================
# Page Config
# ============================
st.set_page_config(
    page_title="End To End Tracking Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================
# Database Setup
# ============================
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

c.execute('''CREATE TABLE IF NOT EXISTS workflow_type (
    well TEXT PRIMARY KEY,
    workflow TEXT
)''')
conn.commit()

# ============================
# User Roles
# ============================
USERS = {
    "user1": "entry",
    "user2": "entry",
    "user3": "entry",
    "viewer1": "view",
    "viewer2": "view",
    "viewer3": "view"
}

username = st.sidebar.text_input("Username")
if username not in USERS:
    st.sidebar.error("User not recognized")
    st.stop()
role = USERS[username]

# ============================
# Well Names and Processes
# ============================
wells = ["SNN-11", "SN-113", "SN-114", "SNN-10", "SR-603", "SN-115",
         "BRNW-106", "SNNORTH11_DEV", "SRM-V36A", "SRM-VE127"]

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

# KPI mapping
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

# ============================
# Sidebar: Well Selection and Workflow
# ============================
st.sidebar.header("Well Selection and Data Entry")
previous_well = st.session_state.get('selected_well', None)
selected_well = st.sidebar.selectbox("Select a Well", wells)
st.session_state['selected_well'] = selected_well

# Load workflow type from DB
c.execute('SELECT workflow FROM workflow_type WHERE well = ?', (selected_well,))
saved_workflow = c.fetchone()
default_workflow = saved_workflow[0] if saved_workflow else "HBF"

selected_workflow = st.sidebar.selectbox("Select Workflow", ["HBF", "HAF"], index=["HBF", "HAF"].index(default_workflow))
st.session_state["workflow_type"] = selected_workflow

if saved_workflow is None or selected_workflow != saved_workflow[0]:
    c.execute('REPLACE INTO workflow_type (well, workflow) VALUES (?, ?)', (selected_well, selected_workflow))
    conn.commit()

# Restore dates from DB
if previous_well != selected_well:
    for process in processes:
        key_start = f"start_{process}"
        key_end = f"end_{process}"
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
        result = c.fetchone()
        st.session_state[key_start] = pd.to_datetime(result[0]).date() if result and result[0] else None
        st.session_state[key_end] = pd.to_datetime(result[1]).date() if result and result[1] else None

# ============================
# Sidebar: Date Inputs
# ============================
if role == "entry":
    for process in processes:
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
            st.sidebar.error(f"Error: Start date must be <= End date for {process}")
        elif start_date and end_date:
            c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                      (selected_well, process, start_date.isoformat(), end_date.isoformat()))
            conn.commit()

# ============================
# Layout Columns
# ============================
col1, col2, col3 = st.columns((2, 7, 2), gap='medium')

# ============================
# Column 1: Well + Donut Charts
# ============================
col1.header(f"Well: {selected_well} ({st.session_state['workflow_type']})")

# --- Ongoing Process Donut ---
c.execute('SELECT process, start_date, end_date FROM process_data WHERE well = ?', (selected_well,))
df_process = pd.DataFrame(c.fetchall(), columns=['process', 'start_date', 'end_date'])
df_process['start_date'] = pd.to_datetime(df_process['start_date'], errors='coerce')
df_process['end_date'] = pd.to_datetime(df_process['end_date'], errors='coerce')

ongoing_process = None
# Case 1: started but not ended
in_progress = df_process[(df_process['start_date'].notna()) & (df_process['end_date'].isna())]
if not in_progress.empty:
    ongoing_process = {'name': in_progress.iloc[0]['process'], 'start_date': in_progress.iloc[0]['start_date']}
else:
    # Case 2: next after last completed
    completed = df_process[df_process['end_date'].notna()].sort_values(by='end_date')
    if not completed.empty:
        last = completed.iloc[-1]['process']
        idx = df_process['process'].tolist().index(last)
        if idx+1 < len(df_process):
            next_proc = df_process.iloc[idx+1]
            ongoing_process = {'name': next_proc['process'], 'start_date': next_proc['start_date']}

# Donut 1
if ongoing_process:
    used_days = (date.today() - ongoing_process['start_date'].date()).days if ongoing_process['start_date'] else 0
    kpi_days = kpi_dict.get(ongoing_process['name'], 120)
    fig_donut1 = px.pie(values=[used_days, max(kpi_days - used_days, 0)],
                         names=['Used', 'Remaining'], hole=0.6)
    fig_donut1.update_traces(textinfo='none')
    fig_donut1.add_annotation(text=f"{(used_days/kpi_days)*100:.1f}%",
                              x=0.5, y=0.5, font_size=18, showarrow=False)
    col1.subheader("Ongoing Process vs KPI")
    col1.plotly_chart(fig_donut1, use_container_width=True)

# Donut 2: 120-day KPI window
c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "Rig Release"))
rig = c.fetchone()
c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "On stream"))
ons = c.fetchone()

if rig and rig[0]:
    start_dt = pd.to_datetime(rig[0]).date()
    if ons and ons[0]:
        used_days = (pd.to_datetime(ons[0]).date() - start_dt).days
    else:
        used_days = (date.today() - start_dt).days
else:
    used_days = 0

kpi_days = 120
remaining = max(kpi_days - used_days, 0)

fig_donut2 = px.pie(values=[used_days, remaining],
                     names=['Used', 'Remaining to KPI'], hole=0.6)
fig_donut2.update_traces(textinfo='none')
fig_donut2.add_annotation(text=f"{(used_days/kpi_days)*100:.1f}%",
                          x=0.5, y=0.5, font_size=18, showarrow=False)
col1.subheader("120-Day Window vs KPI")
col1.plotly_chart(fig_donut2, use_container_width=True)

# ============================
# Column 2: Traffic Light Table
# ============================
progress_data = []
for well in wells:
    c.execute('SELECT process, start_date, end_date FROM process_data WHERE well = ? ORDER BY end_date DESC LIMIT 1', (well,))
    proc = c.fetchone()
    if proc:
        proc_name, start, end = proc
        start_dt = pd.to_datetime(start) if start else None
        end_dt = pd.to_datetime(end) if end else None
        total_days = (end_dt - start_dt).days if start_dt and end_dt else None
        percent_kpi = round((total_days/120)*100,1) if total_days else None
        remaining_days = 120 - total_days if total_days else None
        # Row color traffic light
        if total_days is not None:
            if total_days <= 90:
                row_color = '#32CD32'
            elif total_days <= 120:
                row_color = '#FFD700'
            else:
                row_color = '#FF6347'
        else:
            row_color = '#D3D3D3'
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
            "Current Process": proc_name,
            "Total days on Current Process": total_days,
            "Percentage vs KPI of Current Process": f"{percent_kpi}%" if percent_kpi else None,
            "Remaining Days": remaining_days,
            "Row Color": row_color,
            "Gap/Status": gap_text
        })
    else:
        progress_data.append({
            "Well": well,
            "Current Process": None,
            "Total days on Current Process": None,
            "Percentage vs KPI of Current Process": None,
            "Remaining Days": None,
            "Row Color": '#D3D3D3',
            "Gap/Status": "Missing data"
        })

progress_df = pd.DataFrame(progress_data)

def highlight_remaining(val):
    if isinstance(val,(int,float)):
        if val <= 0:
            return 'background-color: red; color:white'
       


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
