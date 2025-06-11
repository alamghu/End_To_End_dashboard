import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# Database setup
conn = sqlite3.connect('well_processes.db', check_same_thread=False)
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS process_data (
    well TEXT,
    process TEXT,
    start_date TEXT,
    end_date TEXT,
    PRIMARY KEY (well, process)
)
''')
conn.commit()

# Define wells and processes
wells = [f"Well {i+1}" for i in range(10)]
processes = [
    "Handover WLCTF from UWO to GGO",
    "Standalone Activity (SCMT Execution)",
    "On Plot Mechanical Completion",
    "Pre-commissioning (up to SOF)",
    "Unhook",
    "Handover WLCTF from GGO to UWI",
    "Waiting on shared IFS resources",
    "Frac Execution",
    "Re-Hook and commissioning (eSOF)",
    "Plug Removal",
    "On stream"
]

# Configure layout
st.set_page_config(layout="wide")
st.title("Well Process Tracking Dashboard")

# Sidebar
selected_well = st.sidebar.selectbox("Select a well", wells)

# Load current data for selected well
c.execute('SELECT process, start_date, end_date FROM process_data WHERE well = ?', (selected_well,))
data_dict = {row[0]: (row[1], row[2]) for row in c.fetchall()}

# Layout setup
col1, col2, col3 = st.columns([1.5, 2, 1.5])

with col1:
    st.subheader(f"Process Dates for {selected_well}")
    for process in processes:
        clean_key = process.replace(" ", "_").replace("(", "").replace(")", "")
        key_start = f"{selected_well}_{clean_key}_start"
        key_end = f"{selected_well}_{clean_key}_end"

        # Load defaults from DB or session state
        start_val_str, end_val_str = data_dict.get(process, (None, None))
        start_val = pd.to_datetime(start_val_str).date() if start_val_str else None
        end_val = pd.to_datetime(end_val_str).date() if end_val_str else None

        col_process, col_start, col_end, col_clear = st.columns([2, 2, 2, 1])
        col_process.markdown(f"**{process}**")

        with col_start:
            st.session_state[key_start] = st.date_input(
                label="Start",
                value=start_val if start_val else datetime.today().date(),
                key=f"{key_start}_input"
            )

        with col_end:
            st.session_state[key_end] = st.date_input(
                label="End",
                value=end_val if end_val else datetime.today().date(),
                key=f"{key_end}_input"
            )

        with col_clear:
            if st.button("🗑️", key=f"clear_{key_start}"):
                # Clear from session and DB
                c.execute('DELETE FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
                conn.commit()
                st.experimental_rerun()

# Save updated values to DB
for process in processes:
    clean_key = process.replace(" ", "_").replace("(", "").replace(")", "")
    key_start = f"{selected_well}_{clean_key}_start"
    key_end = f"{selected_well}_{clean_key}_end"

    start_val = st.session_state.get(key_start)
    end_val = st.session_state.get(key_end)

    if start_val and end_val:
        c.execute('''
            INSERT OR REPLACE INTO process_data (well, process, start_date, end_date)
            VALUES (?, ?, ?, ?)
        ''', (selected_well, process, start_val.strftime("%Y-%m-%d"), end_val.strftime("%Y-%m-%d")))
        conn.commit()

with col2:
    st.subheader("Recorded Data")
    c.execute('SELECT * FROM process_data WHERE well = ?', (selected_well,))
    df = pd.DataFrame(c.fetchall(), columns=["Well", "Process", "Start Date", "End Date"])
    st.dataframe(df)

with col3:
    st.subheader("Completion Percentage")
    completed = df.dropna().shape[0]
    percent_complete = (completed / len(processes)) * 100
    st.metric("Overall Completion", f"{percent_complete:.0f}%")
