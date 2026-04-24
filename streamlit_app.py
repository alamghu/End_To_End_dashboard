import streamlit as st 
import pandas as pd
import sqlite3
from datetime import date, datetime
import plotly.express as px
import plotly.graph_objects as go

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="End To End Tracking Dashboard",
    page_icon="📈",
    layout="wide"
)

# ---------------- DATABASE ----------------
conn = sqlite3.connect("tracking_data.db", check_same_thread=False)
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

# ---------------- USERS ----------------
USERS = {
    "user1": "MU64275",
    "user2": "entry",
    "user3": "entry"
}

username = st.sidebar.text_input("Username")
if username not in USERS:
    st.stop()

role = USERS[username]

# ---------------- DATA ----------------
wells = ["SNN-11", "SN-113", "SN-114", "SNN-10", "SR-603", "SN-115"]

processes = [
    "Rig Release","WLCTF_ UWO ➔ GGO","Standalone Activity",
    "On Plot Hookup","Pre-commissioning","Unhook",
    "WLCTF_GGO ➔ UWIF","Waiting IFS Resources",
    "Frac Execution","Re-Hook & commissioning",
    "Plug Removal","On stream"
]

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

# ---------------- WELL SELECTION ----------------
st.sidebar.header("Well Selection")
selected_well = st.sidebar.selectbox("Select Well", wells)

# ---------------- RESET ON WELL CHANGE ----------------
if "last_well" not in st.session_state:
    st.session_state["last_well"] = selected_well

if st.session_state["last_well"] != selected_well:
    for key in list(st.session_state.keys()):
        if key.startswith("start_") or key.startswith("end_"):
            st.session_state[key] = None
    st.session_state["last_well"] = selected_well

# ---------------- WORKFLOW ----------------
workflow = st.sidebar.selectbox("Workflow", ["HBF", "HAF"])

# ---------------- SIDEBAR DATA ENTRY ----------------
st.sidebar.markdown("## Process Input")

save_clicked = False

for process in processes:
    st.sidebar.markdown(f"**{process}**")

    start = st.sidebar.date_input(f"Start {process}", key=f"start_{process}")
    end = st.sidebar.date_input(f"End {process}", key=f"end_{process}")

    # SAVE BUTTON (NEW SAFE CONTROL)
    if st.sidebar.button(f"Save {process}", key=f"save_{process}"):
        if start and end:
            c.execute(
                "REPLACE INTO process_data VALUES (?,?,?,?)",
                (selected_well, process, start.isoformat(), end.isoformat())
            )
            conn.commit()
            save_clicked = True

    # LEGACY AUTO-SAVE (kept for compatibility)
    if start and end:
        c.execute(
            "REPLACE INTO process_data VALUES (?,?,?,?)",
            (selected_well, process, start.isoformat(), end.isoformat())
        )
        conn.commit()

# ---------------- LOAD DATA ----------------
chart_data = []
progress_data = []

for well in wells:
    for process in processes:
        c.execute(
            "SELECT start_date, end_date FROM process_data WHERE well=? AND process=?",
            (well, process)
        )
        r = c.fetchone()

        if r and r[0] and r[1]:
            duration = (pd.to_datetime(r[1]) - pd.to_datetime(r[0])).days

            chart_data.append({
                "Well": well,
                "Process": process,
                "Duration": duration,
                "KPI": kpi_dict.get(process, 0)
            })

    # ---------------- CURRENT PROCESS ----------------
    c.execute(
        "SELECT process, start_date, end_date FROM process_data WHERE well=? ORDER BY end_date DESC LIMIT 1",
        (well,)
    )
    last = c.fetchone()

    if last:
        proc, start, end = last
        start_dt = pd.to_datetime(start) if start else None
        end_dt = pd.to_datetime(end) if end else None

        current_days = (end_dt - start_dt).days if start_dt and end_dt else None

        progress_data.append({
            "Well": well,
            "Current Process": proc,
            "Current Process Remaining Days": kpi_dict.get(proc, 0) - current_days if current_days else None,
            "Total days on Well": current_days
        })

progress_df = pd.DataFrame(progress_data)
chart_df = pd.DataFrame(chart_data)

# ---------------- EXECUTIVE SUMMARY ----------------
st.subheader("Executive Summary")

if not progress_df.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Wells", len(progress_df))
    c2.metric("Avg Cycle", f"{progress_df['Total days on Well'].mean():.1f}")
    c3.metric("On Target", f"{len(progress_df[progress_df['Total days on Well'] <= 120])}")

# ---------------- COLUMN 1 ----------------
col1, col2, col3 = st.columns([2,6,2])

col1.subheader(f"Well: {selected_well}")

current = progress_df[progress_df["Well"] == selected_well]

if not current.empty:
    r = current.iloc[0]
    col1.write(f"Process: {r['Current Process']}")
    col1.write(f"Remaining: {r['Current Process Remaining Days']}")

# ---------------- GANTT (FIXED) ----------------
col2.subheader("Gantt View")

df_gantt = pd.read_sql(
    "SELECT * FROM process_data WHERE well=?",
    conn,
    params=(selected_well,)
)

df_gantt["start_date"] = pd.to_datetime(df_gantt["start_date"], errors="coerce")
df_gantt["end_date"] = pd.to_datetime(df_gantt["end_date"], errors="coerce")
df_gantt = df_gantt.dropna()

if not df_gantt.empty:
    fig = px.timeline(df_gantt, x_start="start_date", x_end="end_date", y="process", color="process")
    col2.plotly_chart(fig, use_container_width=True)

# ---------------- KPI CHART ----------------
if not chart_df.empty:
    fig2 = go.Figure()

    for w in chart_df["Well"].unique():
        d = chart_df[chart_df["Well"] == w]
        fig2.add_bar(x=d["Process"], y=d["Duration"], name=w)

    col2.plotly_chart(fig2, use_container_width=True)

# ---------------- GAP ANALYSIS ----------------
col3.subheader("Gap Analysis")

for _, r in progress_df.iterrows():
    if pd.notna(r["Total days on Well"]):
        gap = r["Total days on Well"] - 120
        col3.write(f"{r['Well']}: {'Over' if gap>0 else 'Under'} by {abs(gap)} days")
