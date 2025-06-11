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
            if st.button("🗑️", key=f"clear_{process}"):
                if st.confirm(f"Are you sure you want to remove dates for '{process}'?"):
                    st.session_state[key_start] = None
                    st.session_state[key_end] = None
                    c.execute('DELETE FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
                    conn.commit()
                    st.experimental_rerun()

        if start_date and end_date and start_date > end_date:
            st.sidebar.error(f"Error: Start date must be before or equal to End date for {process}")
        elif start_date and end_date:
            c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                      (selected_well, process, start_date.isoformat(), end_date.isoformat()))
            conn.commit()

col1, col2, col3 = st.columns((1.5, 4.5, 2), gap='medium')

col1.header(f"Well: {selected_well}")
for process in processes[1:]:
    c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, process))
    result = c.fetchone()
    if result and result[0] and result[1]:
        duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
        col1.write(f"{process}: {duration} days")
    else:
        col1.write(f"{process}: Add dates")

col2.header("KPI Visualization and Comparison")
chart_data = []
progress_days = []

for well in wells:
    for process in processes[1:]:
        c.execute('SELECT start_date, end_date FROM process_data WHERE well = ? AND process = ?', (well, process))
        result = c.fetchone()
        if result and result[0] and result[1]:
            duration = max((pd.to_datetime(result[1]) - pd.to_datetime(result[0])).days, 1)
            chart_data.append({'Well': well, 'Process': process, 'Duration': duration})

    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, "Rig Release"))
    rig_rel = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, "On stream"))
    on_stream = c.fetchone()

    if on_stream and on_stream[0]:
        status = "HU Completed, On Stream"
        val = 0
    elif rig_rel and rig_rel[0]:
        val = 120 - (date.today() - pd.to_datetime(rig_rel[0]).date()).days
        status = val
    else:
        val = None
        status = "No Rig Release"

    progress_days.append({"Well": well, "Completion Progress Days": status})

chart_df = pd.DataFrame(chart_data)
if not chart_df.empty:
    fig = px.bar(chart_df, x='Process', y='Duration', color='Well', barmode='group')
    col2.plotly_chart(fig)

progress_days_df = pd.DataFrame(progress_days)

def highlight_days(val):
    if isinstance(val, int):
        if val < 0:
            return 'background-color: red'
        elif val < 60:
            return 'background-color: orange'
        elif 60 <= val <= 120:
            return 'background-color: green'
        else:
            return 'background-color: red'
    return ''

styled_progress_days_df = progress_days_df.style.applymap(highlight_days, subset=["Completion Progress Days"])
col2.write("### Completion Progress Days")
col2.dataframe(styled_progress_days_df, use_container_width=True)

col3.header("Progress Overview & Gap Analysis")
progress_data = []
gap_analysis = []

for well in wells:
    c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (well, 'Rig Release'))
    rig_release = c.fetchone()
    c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (well, 'On stream'))
    on_stream = c.fetchone()
    if rig_release and rig_release[0] and on_stream and on_stream[0]:
        total_days = max((pd.to_datetime(on_stream[0]) - pd.to_datetime(rig_release[0])).days, 1)
        progress = round((total_days / 120) * 100, 1)
        color = "#32CD32" if total_days <= 120 else "#FF6347"
        progress_data.append({"Well": well, "Total Days": total_days, "Completion Percentage": f"{progress}%", "Color": color})
        gap = total_days - 120
        gap_analysis.append(f"{well}: {'Over' if gap > 0 else 'Under'} target by {abs(gap)} days")
    else:
        progress_data.append({"Well": well, "Total Days": None, "Completion Percentage": None, "Color": None})
        gap_analysis.append(f"{well}: Missing Rig Release or On stream dates")

progress_df = pd.DataFrame(progress_data)

if not progress_df.empty:
    def color_progress(val, color):
        return f'background-color: {color}' if color else ''

    display_df = progress_df.drop(columns=["Color"]).copy()
    styled_df = display_df.style.apply(
        lambda x: [color_progress(v, progress_df.loc[x.name, "Color"]) for v in x],
        axis=1
    )
    col3.dataframe(styled_df, use_container_width=True)

col3.write("### Gap Analysis")
for gap in gap_analysis:
    col3.write(gap)

# Donut chart
c.execute('SELECT start_date FROM process_data WHERE well = ? AND process = ?', (selected_well, 'Rig Release'))
rr = c.fetchone()
c.execute('SELECT end_date FROM process_data WHERE well = ? AND process = ?', (selected_well, 'On stream'))
os = c.fetchone()
if os and os[0]:
    remaining = 0
    text_label = "HU Completed, On Stream"
else:
    if rr and rr[0]:
        remaining = 120 - (date.today() - pd.to_datetime(rr[0]).date()).days
        text_label = f"{remaining} days"
    else:
        remaining = None
        text_label = "No Rig Release"

if remaining is not None:
    donut_df = pd.DataFrame({
        "Status": ["Remaining", "Completed"],
        "Days": [remaining if remaining > 0 else 0, 120 - remaining if remaining > 0 else 120]
    })
    fig = px.pie(donut_df, values='Days', names='Status', hole=0.5)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(annotations=[dict(text=text_label, x=0.5, y=0.5, font_size=18, showarrow=False)])
    col1.plotly_chart(fig, use_container_width=True)
