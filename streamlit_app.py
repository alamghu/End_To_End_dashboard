import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import altair as alt
import plotly.express as px

st.set_page_config(
    page_title="End To End Tracking Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

alt.themes.enable("dark")

# Database setup
DB_PATH = "well_tracking.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Define processes for HBF and HAF
PROCESS_FLOW = {
    "HBF": [
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
    ],
    "HAF": [
        "Handover WLCTF from UWO to GGO",
        "Standalone Activity (SCMT Execution)",
        "On Plot Mechanical Completion",
        "Pre-commissioning (up to SOF)",
        "Unhook",
        "Frac Execution",
        "Re-Hook and commissioning (eSOF)",
        "Plug Removal",
        "On stream"
    ]
}

# Dummy KPI data (in days)
KPI_VALUES = {
    "Handover WLCTF from UWO to GGO": 2,
    "Standalone Activity (SCMT Execution)": 3,
    "On Plot Mechanical Completion": 5,
    "Pre-commissioning (up to SOF)": 4,
    "Unhook": 2,
    "Handover WLCTF from GGO to UWI": 2,
    "Waiting on shared IFS resources": 3,
    "Frac Execution": 3,
    "Re-Hook and commissioning (eSOF)": 4,
    "Plug Removal": 2,
    "On stream": 1,
    "Rig Release": 0,
    "Rig Out": 0
}

# Load saved data
cursor.execute("CREATE TABLE IF NOT EXISTS well_data (well TEXT, process TEXT, start_date TEXT, end_date TEXT, workflow TEXT, rig_out TEXT, UNIQUE(well, process))")
conn.commit()

# Sidebar UI
st.sidebar.header("Well Tracking Input")
wells = ["Well-1", "Well-2", "Well-3"]
selected_well = st.sidebar.selectbox("Select Well", wells)
workflow_type = st.sidebar.selectbox("Select Workflow Type", ["HBF", "HAF"])

# Select process list
processes = PROCESS_FLOW[workflow_type]

st.sidebar.markdown(f"### Data Entry for {selected_well} ({workflow_type})")
data = {}

for process in processes + ["Rig Release", "Rig Out"]:
    st.sidebar.markdown(f"**{process}**")
    start = st.sidebar.date_input(f"Start Date - {process}", key=f"{process}_start")
    end = st.sidebar.date_input(f"End Date - {process}", key=f"{process}_end")
    data[process] = {"start": start, "end": end}

# Save to DB
for process, dates in data.items():
    cursor.execute("""
        INSERT OR REPLACE INTO well_data (well, process, start_date, end_date, workflow, rig_out)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (selected_well, process, str(dates["start"]), str(dates["end"]), workflow_type, str(data["Rig Out"]["end"])))
conn.commit()

# Load all well data
df = pd.read_sql_query("SELECT * FROM well_data", conn)
df["start_date"] = pd.to_datetime(df["start_date"])
df["end_date"] = pd.to_datetime(df["end_date"])
df["duration"] = (df["end_date"] - df["start_date"]).dt.days

# Layout Columns
col1, col2 = st.columns([2, 3])

# Column 1: Completion Table + Donut
with col1:
    st.subheader(f"{selected_well} Timeline ({workflow_type})")
    well_df = df[df["well"] == selected_well]
    summary = []
    total_completed_days = 0
    total_kpi_days = 0

    for process in processes:
        row = well_df[well_df["process"] == process]
        if not row.empty:
            duration = int(row["duration"].values[0])
            kpi = KPI_VALUES.get(process, 0)
            total_completed_days += duration
            total_kpi_days += kpi
            summary.append({"Process": process, "Duration": duration, "KPI": kpi})

    summary_df = pd.DataFrame(summary)
    st.dataframe(summary_df, use_container_width=True)

    donut_data = {
        "Status": ["Completed", "Remaining"],
        "Days": [total_completed_days, max(total_kpi_days - total_completed_days, 0)]
    }
    donut_df = pd.DataFrame(donut_data)
    fig = px.pie(donut_df, names="Status", values="Days", hole=0.5,
                 title="Completion vs KPI")
    st.plotly_chart(fig, use_container_width=True)

# Column 2: KPI Chart + Monthly Avg
with col2:
    st.subheader("KPI Comparison")
    kpi_chart_df = df[df["process"].isin(processes)]

    fig = px.bar(kpi_chart_df, x="process", y="duration", color="well",
                 barmode="group", title="Process Duration vs KPI")
    fig.add_scatter(x=list(KPI_VALUES.keys()), y=list(KPI_VALUES.values()),
                    mode="lines+markers", name="KPI", line=dict(color="red", dash="dash"))
    st.plotly_chart(fig, use_container_width=True)

    # Monthly compliance chart
    df["month"] = df["start_date"].dt.to_period("M").astype(str)
    monthly = df[df["process"].isin(processes)].groupby(["month", "well"])["duration"].mean().reset_index()
    st.subheader("Monthly Average Duration per Well")
    fig = px.bar(monthly, x="month", y="duration", color="well", barmode="group",
                 labels={"duration": "Avg Days"})
    st.plotly_chart(fig, use_container_width=True)

    # Summary Insight
    st.markdown("---")
    st.subheader("Monthly Summary")
    recent_month = monthly["month"].max()
    latest = monthly[monthly["month"] == recent_month]
    for _, row in latest.iterrows():
        st.markdown(f"- **{row['well']}** averaged **{row['duration']:.1f} days** per process in {row['month']}")
