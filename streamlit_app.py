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

# ---------------- DATABASE ----------------
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

# ---------------- USERS ----------------
USERS = {
    "user1": "MU64275",
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

# ---------------- DATA ----------------
wells = ["SNN-11", "SN-113", "SN-114", "SNN-10", "SR-603", "SN-115", "BRNW-106", "SNNORTH11_DEV", "SRM-V36A", "SRM-VE127"]

processes = [
    "Rig Release",
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
    "On stream"
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

# ---------------- SIDEBAR ----------------
st.sidebar.header("Well Selection and Data Entry")
selected_well = st.sidebar.selectbox("Select a Well", wells)

if role == "entry":
    for process in processes:
        st.sidebar.markdown(f"**{process}**")
        col1, col2 = st.sidebar.columns(2)

        with col1:
            start_date = st.date_input(f"Start - {process}", key=f"s_{process}")
        with col2:
            end_date = st.date_input(f"End - {process}", key=f"e_{process}")

        if start_date and end_date:
            c.execute(
                "REPLACE INTO process_data VALUES (?,?,?,?)",
                (selected_well, process, start_date.isoformat(), end_date.isoformat())
            )
            conn.commit()

# ---------------- LAYOUT ----------------
col1, col2, col3 = st.columns((1.5, 8.0, 1.0), gap='medium')

# ---------------- LOAD DATA ----------------
chart_data = []
progress_data = []

for well in wells:
    for process in processes:
        c.execute(
            'SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?',
            (well, process)
        )
        result = c.fetchone()

        if result and result[0] and result[1]:
            duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 0)

            chart_data.append({
                "Well": well,
                "Process": process,
                "Duration": duration,
                "KPI": kpi_dict.get(process, 0)
            })

    # Progress tracking
    c.execute('SELECT process, start_date, end_date FROM process_data WHERE well = ? ORDER BY end_date DESC LIMIT 1', (well,))
    proc = c.fetchone()

    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig = c.fetchone()

    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    ons = c.fetchone()

    if proc:
        process_name, start, end = proc

        start_dt = pd.to_datetime(start) if start else None
        end_dt = pd.to_datetime(end) if end else None

        if rig and rig[0]:
            rig_dt = pd.to_datetime(rig[0])
            end_total = pd.to_datetime(ons[0]) if ons and ons[0] else pd.to_datetime(date.today())
            total_days = (end_total - rig_dt).days
        else:
            total_days = None

        current_days = (end_dt - start_dt).days if start_dt and end_dt else None
        kpi = kpi_dict.get(process_name, 120)

        remaining = kpi - current_days if current_days is not None else None

        progress_data.append({
            "Well": well,
            "Current Process": process_name,
            "Total days on Well": total_days,
            "Current Process Remaining Days": remaining,
            "Row Color": "#32CD32"
        })

progress_df = pd.DataFrame(progress_data)
chart_df = pd.DataFrame(chart_data)

# ---------------- EXECUTIVE KPI ----------------
col2.subheader("Executive Summary")

total_wells = len(progress_df)
on_target = progress_df[progress_df["Total days on Well"] <= 120]
avg_days = progress_df["Total days on Well"].mean()

c1, c2, c3 = col2.columns(3)
c1.metric("Total Wells", total_wells)
c2.metric("% On Target", f"{(len(on_target)/total_wells*100):.1f}%" if total_wells else "0%")
c3.metric("Avg Cycle Time", f"{avg_days:.1f} days" if pd.notna(avg_days) else "N/A")

# ---------------- FIXED STYLING (ROOT FIX) ----------------
def highlight_remaining(val):
    try:
        if pd.notna(val):
            val = float(val)
            if val <= 0:
                return 'background-color:red;color:white'
            elif val <= 60:
                return 'background-color:orange'
            else:
                return 'background-color:green'
    except:
        pass
    return ''

def highlight_remaining_column(col):
    if col.name == "Current Process Remaining Days":
        return col.map(highlight_remaining)
    return [''] * len(col)

# ensure column exists
if "Current Process Remaining Days" not in progress_df.columns:
    progress_df["Current Process Remaining Days"] = None

styled_df = progress_df.drop(columns=["Row Color"], errors="ignore").style.apply(
    lambda x: [
        f'background-color:{progress_df["Row Color"].iloc[x.name]}' if "Row Color" in progress_df.columns else ''
        for _ in x
    ],
    axis=1
).apply(highlight_remaining_column, axis=0)

col2.dataframe(styled_df, use_container_width=True)

# ---------------- CURRENT PROCESS PANEL ----------------
col1.subheader("Current Process Status")

if not progress_df.empty:
    latest = progress_df.iloc[0]
    col1.write(f"Process: {latest['Current Process']}")
    col1.write(f"Remaining Days: {latest['Current Process Remaining Days']}")
    col1.progress(0.6)

# ---------------- KPI CHART ----------------
if not chart_df.empty:
    fig = go.Figure()

    for w in chart_df["Well"].unique():
        d = chart_df[chart_df["Well"] == w]
        fig.add_bar(x=d["Process"], y=d["Duration"], name=w)

    fig.add_trace(go.Scatter(
        x=chart_df["Process"].unique(),
        y=[kpi_dict.get(p, 0) for p in chart_df["Process"].unique()],
        mode="lines+markers",
        name="KPI",
        line=dict(color="red")
    ))

    col2.plotly_chart(fig, use_container_width=True)

# ---------------- GANTT ----------------
col2.subheader("Process Timeline (Gantt View)")

df_gantt = pd.read_sql("SELECT * FROM process_data", conn)
df_gantt["start_date"] = pd.to_datetime(df_gantt["start_date"], errors="coerce")
df_gantt["end_date"] = pd.to_datetime(df_gantt["end_date"], errors="coerce")

df_gantt = df_gantt.dropna(subset=["start_date", "end_date"])

if not df_gantt.empty:
    fig_gantt = px.timeline(
        df_gantt,
        x_start="start_date",
        x_end="end_date",
        y="process",
        color="process"
    )
    col2.plotly_chart(fig_gantt, use_container_width=True)

# ---------------- GAP ANALYSIS ----------------
col3.header("Gap Analysis")

for _, row in progress_df.iterrows():
    td = row["Total days on Well"]
    if td:
        gap = td - 120
        col3.write(f"{row['Well']}: {'Over' if gap>0 else 'Under'} by {abs(gap)} days")
    else:
        col3.write(f"{row['Well']}: Missing data")
