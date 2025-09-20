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
    initial_sidebar_state="expanded"
)

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

# Define well names (kept as you had them)
wells = ["SNN-11", "SN-113", "SN-114", "SNN-10", "SR-603", "SN-115", "BRNW-106", "SNNORTH11_DEV", "SRM-V36A", "SRM-VE127"]

# Define process stages (kept your original names/order)
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

# KPI process (kept your original KPI dictionary)
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

    rig_release_date = (st.sidebar.date_input(
        "Rig Release",
        value=default_rig_release,
        key=rig_release_key,
        help="Enter Rig Release Date") if default_rig_release else st.sidebar.date_input("Rig Release", key=rig_release_key))

    if rig_release_date:
        c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                  (selected_well, "Rig Release", rig_release_date.isoformat(), rig_release_date.isoformat()))
        conn.commit()
        st.session_state[f"end_Rig Release"] = rig_release_date

    # Rig Out (note: 'Rig Out' is not in processes list; you store it separately)
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "Rig Out"))
    saved_rigout = c.fetchone()
    rig_out_key = "rig_out"
    default_rig_out = pd.to_datetime(saved_rigout[0]).date() if saved_rigout and saved_rigout[0] else None

    rig_out_date = (st.sidebar.date_input(
        "Rig Out",
        value=default_rig_out,
        key=rig_out_key,
        help="Enter Rig Out Date") if default_rig_out else st.sidebar.date_input("Rig Out", key=rig_out_key))

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
col1, col2, col3 = st.columns((1.5, 8.0, 1.0), gap='medium')

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
# Fetch db rows for the selected well and merge with full process order to preserve sequence
c.execute('SELECT process, start_date, end_date FROM process_data WHERE well = ?', (selected_well,))
rows = c.fetchall()
df_db = pd.DataFrame(rows, columns=['process', 'start_date', 'end_date']) if rows else pd.DataFrame(columns=['process', 'start_date', 'end_date'])
df_full = pd.DataFrame({'process': processes})
df = pd.merge(df_full, df_db, on='process', how='left')
df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce')
df['end_date'] = pd.to_datetime(df['end_date'], errors='coerce')

# ---------- Updated Ongoing Process Logic for Donut Chart ----------
ongoing_process = None

# Case 1: Any process has started but not finished
in_progress = df[(df['start_date'].notna()) & (df['end_date'].isna())]
if not in_progress.empty:
    # pick the first in the defined sequence that is in progress
    ongoing_process = in_progress.iloc[0]['process']
else:
    # Case 2: If no unfinished process, use next process after last completed
    completed = df[df['end_date'].notna()].sort_values(by='end_date')
    if not completed.empty:
        last_completed = completed.iloc[-1]['process']
        try:
            idx = processes.index(last_completed)
            ongoing_process = processes[idx + 1] if idx + 1 < len(processes) else None
        except ValueError:
            ongoing_process = None
    else:
        # Case 3: Nothing started yet → first process
        ongoing_process = processes[0] if len(processes) > 0 else None

# Calculate KPI and Remaining Days
if ongoing_process:
    row = df[df['process'] == ongoing_process].iloc[0]
    start_date = row['start_date']
    kpi_value = kpi_dict.get(ongoing_process, 1)  # fallback to 1 to avoid div by zero

    # handle KPI 0 (if defined as 0 in dictionary) - treat as 1 for calculation but will show 0% if needed
    if kpi_value <= 0:
        kpi_value_calc = 1
    else:
        kpi_value_calc = kpi_value

    if pd.notna(start_date):
        elapsed_days = (date.today() - start_date.date()).days
        remaining_days = max(kpi_value - elapsed_days, 0) if kpi_value > 0 else 0
        percentage_remaining = round((remaining_days / kpi_value_calc) * 100, 1) if kpi_value_calc > 0 else 0
        label = f"{ongoing_process}\n{remaining_days} days left ({percentage_remaining}%)"
    else:
        remaining_days = kpi_value if kpi_value > 0 else 0
        percentage_remaining = 100 if kpi_value > 0 else 0
        label = f"{ongoing_process}\nNot Started"
else:
    remaining_days = 0
    kpi_value = 1
    label = "No Ongoing Process"

# Draw donut chart
fig_donut = px.pie(values=[remaining_days, max(kpi_value - remaining_days, 0)], names=['Remaining', 'Elapsed'], hole=0.6)
fig_donut.update_traces(textinfo='none')
fig_donut.add_annotation(text=label, x=0.5, y=0.5, font_size=18, showarrow=False)
col1.plotly_chart(fig_donut, use_container_width=True)
# -------------------------------------------------------------------
# 2nd Donut Chart in col1 (120-day window)
c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "Rig Release"))
rig = c.fetchone()
c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "On stream"))
onstream = c.fetchone()

kpi_days = 120

if onstream and onstream[0]:
    used_days = kpi_days
    label2 = "HU Completed, On Stream"
elif rig and rig[0]:
    delta = (date.today() - pd.to_datetime(rig[0]).date()).days
    used_days = min(delta, kpi_days)  # cap at KPI
    label2 = f"{used_days} days"
else:
    used_days = 0
    label2 = "No Rig Date"

# --- Donut chart: % Used vs KPI (120 days) ---
fig_donut2 = px.pie(
    values=[used_days, max(kpi_days - used_days, 0)],
    names=['Used', 'Remaining to KPI'],
    hole=0.6
)
fig_donut2.update_traces(textinfo='none')
fig_donut2.add_annotation(
    text=f"{(used_days/kpi_days)*100:.1f}%", 
    x=0.5, y=0.5, font_size=18, showarrow=False
)
col1.plotly_chart(fig_donut2, use_container_width=True)



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
            chart_data.append({'Well': well, 'Process': process, 'Duration': duration, 'KPI': kpi_dict.get(process)})

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
    fig = go.Figure()

    # Add bar traces per well
    for well_name in chart_df['Well'].unique():
        df_w = chart_df[chart_df['Well'] == well_name]
        fig.add_trace(go.Bar(x=df_w['Process'], y=df_w['Duration'], name=well_name))

    # Add KPI line across all processes (uses the unique processes present in chart_df)
    processes_unique = chart_df['Process'].unique()
    kpi_values = [kpi_dict.get(proc, 0) for proc in processes_unique]
    fig.add_trace(go.Scatter(
        x=processes_unique,
        y=kpi_values,
        mode='lines+markers',
        name='KPI',
        line=dict(color='red', dash='solid'),
        marker=dict(color='red')
    ))

    fig.update_layout(barmode='group', xaxis_title='Process', yaxis_title='Days')
    col2.plotly_chart(fig, use_container_width=True)
else:
    col2.write("No chart data available. Add start/end dates for processes to see KPI comparison.")

# Prepare data for Column 2 table
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

        # Percentage vs Process KPI ((of current process)) — here you used 120 as reference previously.
        percent_kpi = round((total_days / 120) * 100, 1) if total_days is not None else None

        # Remaining days against KPI (of current process)
        remaining_days = 120 - total_days if total_days is not None else None

        # Month of Onstream
        c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
        onstream = c.fetchone()
        month_onstream = pd.to_datetime(onstream[0]).strftime('%B') if onstream and onstream[0] else None

        # Completion color 
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
            "Percentage vs KPI of Current Process": f"{percent_kpi}%" if percent_kpi is not None else None,
            "Remaining Days": remaining_days,
            "Month of Onstream": month_onstream,
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
            "Month of Onstream": None,
            "Row Color": None,
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
#-----------------------------------------------------------------------------------------------------------

# Column 3: Gap Analysis
col3.header("Gap Analysis")
gap_analysis = []
for gap in gap_analysis:
    col3.write(gap)
