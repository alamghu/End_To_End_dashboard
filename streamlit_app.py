import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime
import plotly.express as px

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
kpi_days = {
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
col1, col2, col3 = st.columns((2.5, 5.5, 2), gap='medium')

# Column 1: Well name + workflow
col1.header(f"Well: {selected_well} ({st.session_state['workflow_type']})")
total_duration = 0
for process in processes[1:]:
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
    result = c.fetchone()
    if result and result[0] and result[1]:
        duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
        total_duration += duration
        col1.write(f"{process}: {duration} days (KPI: {kpi_days.get(process, '-')})")
    else:
        col1.write(f"{process}: Add dates (KPI: {kpi_days.get(process, '-')})")

# Donut Chart in col1
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

# Column 2: KPI Visualization + Progress Days Table
col2.header("KPI Visualization and Comparison")
chart_data = []
progress_day_data = []

for well in wells:
    for process in processes[1:]:
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, process))
        result = c.fetchone()
        if result and result[0] and result[1]:
            duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
            chart_data.append({'Well': well, 'Process': process, 'Duration': duration, 'KPI': kpi_days.get(process)})

    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, "Rig Release"))
    rig = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, "On stream"))
    ons = c.fetchone()

    if ons and ons[0]:
        progress_day_data.append({"Well": well, "Completion Progress Days": "HU Completed, On Stream"})
    elif rig and rig[0]:
        delta = 120 - (date.today() - pd.to_datetime(rig[0]).date()).days
        progress_day_data.append({"Well": well, "Completion Progress Days": delta})
    else:
        progress_day_data.append({"Well": well, "Completion Progress Days": None})

chart_df = pd.DataFrame(chart_data)
if not chart_df.empty:
    fig = px.bar(chart_df, x='Process', y='Duration', color='Well', barmode='group', title='Process Visualization')
    col2.plotly_chart(fig)

progress_day_df = pd.DataFrame(progress_day_data)

def highlight(val):
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

col2.dataframe(progress_day_df.style.applymap(highlight), use_container_width=True)


    
# Column 3: Completion Percentage and Gap Analysis
col3.header("Progress Overview & Gap Analysis")
progress_data = []
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
        progress_data.append({"Well": well, "Total Days": total_days, "Completion Percentage": f"{progress}%", "Color": color})
        gap = total_days - 120
        gap_analysis.append(f"{well}: {'Over' if gap > 0 else 'Under'} target by {abs(gap)} days")
    else:
        progress_data.append({"Well": well, "Total Days": None, "Completion Percentage": None, "Color": None})
        gap_analysis.append(f"{well}: Missing Rig Release or On stream dates")

progress_df = pd.DataFrame(progress_data)

if not progress_df.empty:
    def color_cells(val, color):
        return f'background-color: {color}' if color else ''

    styled_df = progress_df.drop(columns=["Color"]).style.apply(
        lambda x: [color_cells(v, progress_df.loc[x.name, "Color"]) for v in x], axis=1)
    col3.dataframe(styled_df, use_container_width=True)

col3.write("### Gap Analysis")
for gap in gap_analysis:
    col3.write(gap)   
