# Updated Streamlit app 11/06/2025 @ 8am

import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime
import altair as alt
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="End To End Tracking Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded")

alt.themes.enable("dark")

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
    "On stream"
]

# Layout
st.sidebar.header("Well Selection and Data Entry")
previous_well = st.session_state.get('selected_well', None)
selected_well = st.sidebar.selectbox("Select a Well", wells)
st.session_state['selected_well'] = selected_well

# Load saved Rig Release date for selected well (for default input)
c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "Rig Release"))
rig_release_row = c.fetchone()
if rig_release_row and rig_release_row[0]:
    rig_release_default = pd.to_datetime(rig_release_row[0]).date()
else:
    rig_release_default = None  # no default, user must pick

if role == "entry":
    # Rig Release - Single Date Input with default or empty
    rig_release_key = "rig_release"
    rig_release_date = st.sidebar.date_input(
        "Rig Release",
        value=rig_release_default if rig_release_default else date.today(),
        key=rig_release_key,
        help="Enter Rig Release Date"
    )

    # Save Rig Release immediately (start_date = end_date for rig release)
    c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
              (selected_well, "Rig Release", rig_release_date.isoformat(), rig_release_date.isoformat()))
    conn.commit()

    # Also keep end date session state consistent for Rig Release
    st.session_state[f"end_Rig Release"] = rig_release_date

    # Process Data Entry for other processes
    for process in processes[1:]:
        key_start = f"start_{process}"
        key_end = f"end_{process}"
        st.sidebar.markdown(f"**{process}**")
        col_start, col_end = st.sidebar.columns(2)

        with col_start:
            # Provide default value from session state or fallback
            default_start = st.session_state.get(key_start, None)
            start_date = st.date_input(f"Start - {process}", value=default_start, key=key_start)

        with col_end:
            default_end = st.session_state.get(key_end, None)
            end_date = st.date_input(f"End - {process}", value=default_end, key=key_end)

        # Validation: Start date must be before or equal end date
        if start_date and end_date and start_date > end_date:
            st.sidebar.error(f"Error: Start date must be before or equal to End date for {process}")
        else:
            # Save to DB immediately if valid
            if start_date and end_date:
                c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                          (selected_well, process, start_date.isoformat(), end_date.isoformat()))
                conn.commit()

# Visualization columns
col1, col2, col3 = st.columns((1.5, 4.5, 2), gap='medium')

# Column 1: Well being updated (exclude Rig Release)
col1.header(f"Well: {selected_well}")
for process in processes[1:]:
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
    result = c.fetchone()
    if result and result[0] and result[1]:
        duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
        col1.write(f"{process}: {duration} days")
    else:
        col1.write(f"{process}: Add dates")

# Calculate Remaining Days for Donut Chart: 120 - (today - Rig Release)
today = date.today()
remaining_days = None
if rig_release_default:
    days_passed = (today - rig_release_default).days
    remaining_days = 120 - days_passed
else:
    # Try to fetch from DB again if rig_release_default was None
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, "Rig Release"))
    rr = c.fetchone()
    if rr and rr[0]:
        rig_date = pd.to_datetime(rr[0]).date()
        days_passed = (today - rig_date).days
        remaining_days = 120 - days_passed

if remaining_days is not None:
    # Define color based on remaining_days
    if remaining_days > 120:
        rem_color = "#FF0000"  # Red
    elif remaining_days > 60:
        rem_color = "#FFA500"  # Amber
    else:
        rem_color = "#32CD32"  # Green

    # Donut chart figure
    fig_donut = go.Figure(go.Pie(
        values=[max(remaining_days, 0), max(120 - max(remaining_days, 0), 0)],
        labels=["Remaining Days", "Elapsed Days"],
        hole=0.6,
        marker_colors=[rem_color, "#444444"],
        sort=False,
        direction='clockwise',
        textinfo='none'
    ))
    fig_donut.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        showlegend=False,
        annotations=[dict(text=f"{remaining_days} days", x=0.5, y=0.5, font_size=20, showarrow=False)]
    )
    col1.plotly_chart(fig_donut, use_container_width=True)
else:
    col1.write("Rig Release date not set")

# Column 2: KPI Visualization and Comparison (exclude Rig Release)
col2.header("KPI Visualization and Comparison")

# Build chart data as before
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
    col2.plotly_chart(fig)

# Add the new table with well names and "Completion Progress Days"
col2.write("### Completion Progress Days")
table_well_names = wells
# Calculate Completion Progress Days per well = 120 - (today - Rig Release)
completion_progress_days = []
for well in wells:
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, "Rig Release"))
    rr = c.fetchone()
    if rr and rr[0]:
        rr_date = pd.to_datetime(rr[0]).date()
        days_passed = (today - rr_date).days
        val = 120 - days_passed
    else:
        val = None
    completion_progress_days.append(val)

# Build dataframe for the table
table_df = pd.DataFrame([table_well_names, completion_progress_days],
                        index=["Well Name", "Completion Progress Days"])

# Transpose for better display (wells as rows)
table_df = table_df.T
table_df.columns = ["Well Name", "Completion Progress Days"]

# Coloring function
def color_days(val):
    if val is None:
        color = ""
    elif val > 120:
        color = "background-color: #FF6347"  # Red
    elif 60 < val <= 120:
        color = "background-color: #FFA500"  # Amber
    elif val <= 60:
        color = "background-color: #32CD32"  # Green
    else:
        color = ""
    return color

styled_table = table_df.style.applymap(color_days, subset=["Completion Progress Days"])

col2.dataframe(styled_table, use_container_width=True)

# Column 3: Progress Overview & Gap Analysis
col3.header("Progress Overview & Gap Analysis")

progress_data = []
gap_analysis = []
for well in wells:
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig_release = c.fetchone()
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    on_stream = c.fetchone()
    if rig_release and rig_release[0] and on_stream and on_stream[1]:
        total_days = max((pd.to_datetime(on_stream[1]) - pd.to_datetime(rig_release[0])).days, 1)
        completion_percentage = round((total_days / 120) * 100, 1)
        # Clamp completion percentage if needed
        # completion_percentage = min(completion_percentage, 100)
        # Color based on total_days (same criteria)
        if total_days > 120:
            color = "#FF6347"  # Red
        elif 60 < total_days <= 120:
            color = "#FFA500"  # Amber
        else:
            color = "#32CD32"  # Green
        progress_data.append({
            "Well": well,
            "Total Days": total_days,
            "Completion Percentage": f"{completion_percentage} %",  # add unit here
            "Color": color
        })
        gap = total_days - 120
        gap_analysis.append(f"{well}: {'Over' if gap > 0 else 'Under'} target by {abs(gap)} days")
    else:
        progress_data.append({"Well": well, "Total Days": None, "Completion Percentage": None, "Color": None})
        gap_analysis.append(f"{well}: Missing Rig Release or On stream dates")

progress_df = pd.DataFrame(progress_data)

if not progress_df.empty:
    # Show colored completion percentage column only (drop Total Days and Color in display)
    display_df = progress_df[["Well", "Completion Percentage"]].copy()

    def color_completion(val):
        # Get the color from progress_df by matching Well
        well = progress_df.loc[display_df["Completion Percentage"] == val, "Well"].values
        # fallback color
        ccolor = ""
        if not well.size:
            return ""
        else:
            # find the color for the well from progress_df
            color_row = progress_df[progress_df["Well"] == well[0]]
            if not color_row.empty:
                ccolor = color_row.iloc[0]["Color"]
        return f"background-color: {ccolor}" if ccolor else ""

    # Apply color row-wise to the Completion Percentage column
    styled_df = display_df.style.applymap(
        lambda val: color_completion(val),
        subset=["Completion Percentage"]
    )

    col3.dataframe(styled_df, use_container_width=True)

col3.write("### Gap Analysis")
for gap in gap_analysis:
    col3.write(gap)
