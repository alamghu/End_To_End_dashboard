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

wells = ["SNN-11", "SN-113", "SN-114", "SNN-10", "SR-603", "SN-115", "BRNW-106", "SNNORTH11_DEV", "SRM-V36A", "SRM-VE127"]

processes = ["Rig Release",
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
    "On stream"]

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
        if result:
            start_val = pd.to_datetime(result[0]).date() if result[0] else None
            end_val = pd.to_datetime(result[1]).date() if result[1] else None
        else:
            start_val = None
            end_val = None
        st.session_state[key_start] = start_val
        st.session_state[key_end] = end_val

if role == "entry":
    rig_release_key = "rig_release"
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "Rig Release"))
    result = c.fetchone()
    existing_rig_release = pd.to_datetime(result[0]).date() if result and result[0] else None

    rig_release_date = st.sidebar.date_input(
        "Rig Release",
        value=existing_rig_release if existing_rig_release else None,
        key=rig_release_key,
        help="Enter Rig Release Date"
    )

    if rig_release_date:
        c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                  (selected_well, "Rig Release", rig_release_date.isoformat(), rig_release_date.isoformat()))
        conn.commit()
        st.session_state[f"end_Rig Release"] = rig_release_date

    for process in processes[1:]:
        key_start = f"start_{process}"
        key_end = f"end_{process}"
        st.sidebar.markdown(f"**{process}**")
        col_start, col_end, col_clear = st.sidebar.columns([4, 4, 1])

        with col_start:
            default_start = st.session_state.get(key_start, None)
            start_date = st.date_input(f"Start - {process}", value=default_start, key=key_start)

        with col_end:
            default_end = st.session_state.get(key_end, None)
            end_date = st.date_input(f"End - {process}", value=default_end, key=key_end)

        with col_clear:
            confirm_key = f"confirm_clear_{process}"
            if st.button("🗑️", key=f"clear_{process}"):
                st.session_state[confirm_key] = True

            if st.session_state.get(confirm_key, False):
                st.warning(f"Confirm removal of dates for '{process}'?")
                confirm_col1, confirm_col2 = st.columns([1, 1])
                with confirm_col1:
                    if st.button("✅ Yes", key=f"yes_{process}"):
                        st.session_state[key_start] = None
                        st.session_state[key_end] = None
                        c.execute('DELETE FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
                        conn.commit()
                        st.session_state[confirm_key] = False
                        st.experimental_rerun()
                with confirm_col2:
                    if st.button("❌ No", key=f"no_{process}"):
                        st.session_state[confirm_key] = False

        if start_date and end_date and start_date > end_date:
            st.sidebar.error(f"Error: Start date must be before or equal to End date for {process}")
        elif start_date and end_date:
            c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                      (selected_well, process, start_date.isoformat(), end_date.isoformat()))
            conn.commit()
            
