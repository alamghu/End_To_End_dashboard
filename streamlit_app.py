import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
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
wells = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliet"]

# Define process stages
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

def load_well_dates(well):
    """Load process dates from DB into session_state for the selected well."""
    for process in processes:
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, process))
        row = c.fetchone()
        if row:
            start = pd.to_datetime(row[0]).date() if row[0] else None
            end = pd.to_datetime(row[1]).date() if row[1] else None
            st.session_state[f"start_{process}"] = start
            st.session_state[f"end_{process}"] = end
        else:
            st.session_state[f"start_{process}"] = None
            st.session_state[f"end_{process}"] = None

# Well selection
selected_well = st.sidebar.selectbox("Select a Well", wells)

# Load data on well switch
if ('loaded_well' not in st.session_state) or (st.session_state['loaded_well'] != selected_well):
    st.session_state['loaded_well'] = selected_well
    load_well_dates(selected_well)

# Sidebar inputs for Rig Release (single date)
st.sidebar.markdown("### Rig Release Date")
rig_release_key = "start_Rig Release"
rig_release_date = st.sidebar.date_input(
    "Rig Release",
    value=st.session_state.get(rig_release_key, date.today()),
    key=rig_release_key,
    help="Enter Rig Release Date"
)

# Save Rig Release immediately
c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)', (selected_well, "Rig Release", rig_release_date.isoformat(), rig_release_date.isoformat()))
conn.commit()
st.session_state[rig_release_key] = rig_release_date
st.session_state[f"end_Rig Release"] = rig_release_date  # end = start for Rig Release

# Only entry role can input process dates
if role == "entry":
    st.sidebar.markdown("### Process Dates Entry")

    for process in processes[1:]:
        col_start, col_end = st.sidebar.columns(2)
        start_key = f"start_{process}"
        end_key = f"end_{process}"

        # Get current values or None
        start_val = st.session_state.get(start_key, None)
        end_val = st.session_state.get(end_key, None)

        with col_start:
            start_date = st.date_input(
                f"Start\n{process}",
                value=start_val if start_val else None,
                key=start_key,
                help="Add a date" if start_val is None else None
            )

        with col_end:
            # Disable end date input if no start date
            disabled = start_date is None
            end_date = st.date_input(
                f"End\n{process}",
                value=end_val if end_val else None,
                key=end_key,
                disabled=disabled,
                help="Add start date first" if disabled else ("Add a date" if end_val is None else None)
            )

        # Validation: start must be <= end
        if end_date is not None and start_date is not None and end_date < start_date:
            st.sidebar.error(f"End date cannot be earlier than Start date for {process}")
            # Reset end date to None in session state (do not save invalid)
            st.session_state[end_key] = None
        else:
            # Save valid dates to DB and session_state
            if start_date is not None and end_date is not None:
                c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)', (selected_well, process, start_date.isoformat(), end_date.isoformat()))
                conn.commit()
                st.session_state[start_key] = start_date
                st.session_state[end_key] = end_date
            elif start_date is not None and end_date is None:
                # Save start date only with NULL end date
                c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)', (selected_well, process, start_date.isoformat(), None))
                conn.commit()
                st.session_state[start_key] = start_date
                st.session_state[end_key] = None
            else:
                # No start date, clear DB for this process for this well
                c.execute('DELETE FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
                conn.commit()
                st.session_state[start_key] = None
                st.session_state[end_key] = None

# Layout: 3 columns with widths and gap
col1, col2, col3 = st.columns((1.5, 4.5, 2), gap='medium')

# --- Column 1: Well being updated (exclude Rig Release) ---
col1.header(f"Well: {selected_well}")
for process in processes[1:]:
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
    result = c.fetchone()
    if result and result[0] and result[1]:
        duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
        col1.write(f"{process}: {duration} days")
    else:
        col1.write(f"{process}: Incomplete")

# --- Column 2: KPI Visualization and Comparison (exclude Rig Release) ---
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
    col2.plotly_chart(fig, use_container_width=True)

# --- Column 3: Progress Overview & Gap Analysis ---

col3.header("Progress Overview & Gaps Analysis")

progress_data = []
gap_analysis = []

for well in wells:
    # Get Rig Release and On stream dates
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig_release = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    on_stream = c.fetchone()

    if rig_release and rig_release[0] and on_stream and on_stream[0]:
        rig_date = pd.to_datetime(rig_release[0]).date()
        on_stream_date = pd.to_datetime(on_stream[0]).date()
        total_days = max((on_stream_date - rig_date).days, 1)
        progress = (total_days / 120) * 100  # progress % based on 120 days target

        # Color logic
        color = "green" if total_days <= 120 else "red"
        progress_data.append({'Well': well, 'Total Days': total_days, 'Progress %': progress, 'Color': color})

        # Gap analysis: days delayed compared to 120-day target
        gap = total_days - 120
        gap_analysis.append({'Well': well, 'Gap (days)': gap})

if progress_data:
    progress_df = pd.DataFrame(progress_data).sort_values(by='Total Days')
    for idx, row in progress_df.iterrows():
        col3.write(f"**{row['Well']}** - Total Days: {row['Total Days']} - Progress: {row['Progress %']:.1f}%")
        col3.progress(min(row['Progress %'], 100), text=None)

    col3.markdown("---")
    col3.subheader("Gap Analysis (vs 120 days target)")
    gap_df = pd.DataFrame(gap_analysis).sort_values(by='Gap (days)', ascending=False)
    for idx, row in gap_df.iterrows():
        if row['Gap (days)'] > 0:
            col3.error(f"{row['Well']} is delayed by {row['Gap (days)']} days")
        else:
            col3.success(f"{row['Well']} is on track or ahead")

# --- Footer ---
st.markdown("---")
st.caption(f"User: {username} (Role: {role}) | Data saved immediately | Switching wells loads saved data.")
