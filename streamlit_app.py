import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
import plotly.express as px
import plotly.graph_objects as go

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
    "user1": "entry",
    "user2": "entry",
    "user3": "entry",
    "viewer1": "view"
}

username = st.sidebar.text_input("Username")
if username not in USERS:
    st.sidebar.error("User not recognized")
    st.stop()

role = USERS[username]

# ---------------- DATA ----------------
wells = ["SNN-11","SN-113","SN-114","SNN-10","SR-603","SN-115","BRNW-106","SNNORTH11_DEV","SRM-V36A","SRM-VE127"]

processes = [
    "Rig Release","WLCTF_ UWO ➔ GGO","Standalone Activity",
    "On Plot Hookup","Pre-commissioning","Unhook",
    "WLCTF_GGO ➔ UWIF","Waiting IFS Resources",
    "Frac Execution","Re-Hook & commissioning",
    "Plug Removal","On stream"
]

kpi_dict = {
    "Rig Release":4,
    "WLCTF_ UWO ➔ GGO":15,
    "Standalone Activity":5,
    "On Plot Hookup":35,
    "Pre-commissioning":7,
    "Unhook":8,
    "WLCTF_GGO ➔ UWIF":0,
    "Waiting IFS Resources":14,
    "Frac Execution":26,
    "Re-Hook & commissioning":8,
    "Plug Removal":1,
    "On stream":1
}

# ---------------- SIDEBAR ----------------
st.sidebar.header("Well Selection and Data Entry")
selected_well = st.sidebar.selectbox("Select a Well", wells)

if role == "entry":
    for process in processes:
        st.sidebar.markdown(f"**{process}**")
        col1, col2 = st.sidebar.columns(2)

        with col1:
            start = st.date_input(f"Start - {process}", key=f"s_{process}")
        with col2:
            end = st.date_input(f"End - {process}", key=f"e_{process}")

        if start and end:
            c.execute("REPLACE INTO process_data VALUES (?,?,?,?)",
                      (selected_well, process, start.isoformat(), end.isoformat()))
            conn.commit()

# ---------------- LAYOUT ----------------
col1, col2, col3 = st.columns((1.5, 8.0, 1.0))

# ---------------- COLUMN 1 ----------------
col1.header(f"Well: {selected_well}")

# ---------------- COLUMN 2 ----------------
col2.header("KPI Visualization and Comparison")

chart_data = []

for well in wells:
    for process in processes:
        c.execute("SELECT start_date,end_date FROM process_data WHERE well=? AND process=?",(well,process))
        r = c.fetchone()

        if r and r[0] and r[1]:
            duration = max((pd.to_datetime(r[1]) - pd.to_datetime(r[0])).days,1)
            chart_data.append({
                "Well":well,
                "Process":process,
                "Duration":duration,
                "KPI":kpi_dict.get(process,0)
            })

chart_df = pd.DataFrame(chart_data)

if not chart_df.empty:
    fig = go.Figure()

    for w in chart_df['Well'].unique():
        d = chart_df[chart_df['Well']==w]
        fig.add_bar(x=d['Process'], y=d['Duration'], name=w)

    fig.add_scatter(
        x=chart_df['Process'].unique(),
        y=[kpi_dict.get(p,0) for p in chart_df['Process'].unique()],
        mode='lines+markers',
        name='KPI',
        line=dict(color='red')
    )

    col2.plotly_chart(fig, use_container_width=True)

# ---------------- PROGRESS TABLE ----------------
progress_data = []

for well in wells:
    c.execute('SELECT process, start_date, end_date FROM process_data WHERE well = ? ORDER BY end_date DESC LIMIT 1', (well,))
    proc = c.fetchone()

    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    onstream = c.fetchone()

    if proc:
        process_name, start, end = proc
        start_dt = pd.to_datetime(start) if start else None
        end_dt = pd.to_datetime(end) if end else None

        if rig and rig[0]:
            rig_dt = pd.to_datetime(rig[0])
            end_total = pd.to_datetime(onstream[0]) if onstream and onstream[0] else pd.to_datetime(date.today())
            total_days = max((end_total - rig_dt).days, 1)
        else:
            total_days = None

        total_current = (end_dt - start_dt).days if start_dt is not None and end_dt is not None else None
        kpi = kpi_dict.get(process_name,120)

        remaining = kpi - total_current if total_current is not None else None

        if total_days:
            if total_days <= 100:
                color = '#32CD32'
            elif total_days <= 120:
                color = '#FFD700'
            else:
                color = '#FF6347'
        else:
            color = '#cccaca'

        progress_data.append({
            "Well": well,
            "Current Process": process_name,
            "Total days on Well": total_days,
            "Current Process Remaining Days": remaining,
            "Row Color": color
        })

progress_df = pd.DataFrame(progress_data)

# ---------------- FIXED STYLING ----------------
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
    if col.name == 'Current Process Remaining Days':
        return col.map(highlight_remaining)
    return [''] * len(col)

col2.subheader("Well Progress Dashboard")

if not progress_df.empty:
    styled_df = progress_df.drop(columns=["Row Color"]).style.apply(
        lambda x: [f'background-color:{progress_df.loc[x.name,"Row Color"]}' for _ in x], axis=1
    ).apply(highlight_remaining_column, axis=0)

    col2.dataframe(styled_df, use_container_width=True)

# ---------------- NEW FEATURES (NON-BREAKING) ----------------

# Progress Bars
col2.subheader("Progress Bars per Well")
for _, row in progress_df.iterrows():
    if row["Total days on Well"]:
        progress = min(row["Total days on Well"]/120,1)
        col2.write(f"{row['Well']} ({row['Total days on Well']} days)")
        col2.progress(progress)

# KPI Alerts
col2.subheader("KPI Alerts")
for _, row in progress_df.iterrows():
    td = row["Total days on Well"]
    if td:
        if td > 120:
            col2.error(f"{row['Well']} OVER KPI by {td-120} days")
        elif td > 100:
            col2.warning(f"{row['Well']} nearing KPI")
        else:
            col2.success(f"{row['Well']} within KPI")

# Fast Table (No Styler)
col2.subheader("Fast View (No Styling)")
col2.dataframe(progress_df.drop(columns=["Row Color"]), use_container_width=True)

# ---------------- COLUMN 3 ----------------
col3.header("Gap Analysis")

for _, row in progress_df.iterrows():
    td = row["Total days on Well"]
    if td:
        gap = td - 120
        col3.write(f"{row['Well']}: {'Over' if gap>0 else 'Under'} by {abs(gap)} days")
    else:
        col3.write(f"{row['Well']}: Missing data")
