"""
Refactored End-to-End Tracking Dashboard for Well-Completion Process Tracking
Optimized for executive-level stakeholders with enhanced visualizations and KPI tracking.

Key improvements:
- Bulk database reads with caching
- Centralized CONFIG dictionary
- Session state-based authentication
- Plotly gauge and Gantt visualizations
- Executive KPI cards
- Gap analysis with delay reasons
- Modular structure with helper functions
"""

import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import calendar

# ============================================================================
# CONFIGURATION SECTION
# ============================================================================

CONFIG = {
    "TOTAL_KPI_DAYS": 120,
    "COLOR_ON_TRACK": "#2ecc71",  # Green
    "COLOR_AT_RISK": "#f39c12",   # Amber
    "COLOR_OVERDUE": "#e74c3c",   # Red
    "FONT_SIZE_TITLE": 24,
    "FONT_SIZE_SUBTITLE": 16,
    "CACHE_TTL": 60,  # seconds
}

# Hard-coded users (flagged for security: should use environment variables or secure vault)
USERS = {
    "user1": "MU64275",
    "user2": "entry",
    "user3": "entry",
    "viewer1": "view",
    "viewer2": "view",
    "viewer3": "view"
}

# Well names
WELLS = ["SNN-11", "SN-113", "SN-114", "SNN-10", "SR-603", "SN-115", "BRNW-106", "SNNORTH11_DEV", "SRM-V36A", "SRM-VE127"]

# Process stages in defined order
PROCESSES = [
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

# KPI dictionary (days per process)
KPI_DICT = {
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

# Delay reason categories
DELAY_REASONS = ["Logistics", "Permits", "Equipment", "Weather", "3rd-Party", "Resource", "HSE", "Other"]

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="End To End Tracking Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# DATABASE HELPERS (with caching)
# ============================================================================

@st.cache_resource
def get_db_connection():
    """Get cached database connection."""
    conn = sqlite3.connect('tracking_data.db', check_same_thread=False)
    return conn

def init_db():
    """Initialize database tables if they don't exist."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Process data table
    c.execute('''CREATE TABLE IF NOT EXISTS process_data (
        well TEXT,
        process TEXT,
        start_date TEXT,
        end_date TEXT,
        PRIMARY KEY (well, process)
    )''')
    
    # Workflow type table
    c.execute('''CREATE TABLE IF NOT EXISTS workflow_type (
        well TEXT PRIMARY KEY,
        workflow TEXT
    )''')
    
    # Delay reasons table (NEW)
    c.execute('''CREATE TABLE IF NOT EXISTS delay_reasons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        well TEXT,
        process TEXT,
        reason TEXT,
        days INTEGER,
        note TEXT,
        created_at TEXT,
        FOREIGN KEY (well, process) REFERENCES process_data(well, process)
    )''')
    
    conn.commit()

@st.cache_data(ttl=CONFIG["CACHE_TTL"])
def load_all_process_data():
    """Load all process data in a single query and cache it."""
    conn = get_db_connection()
    df = pd.read_sql('SELECT well, process, start_date, end_date FROM process_data', conn)
    if df.empty:
        df = pd.DataFrame(columns=['well', 'process', 'start_date', 'end_date'])
    else:
        df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce')
        df['end_date'] = pd.to_datetime(df['end_date'], errors='coerce')
    return df

@st.cache_data(ttl=CONFIG["CACHE_TTL"])
def load_workflow_data():
    """Load workflow type data."""
    conn = get_db_connection()
    df = pd.read_sql('SELECT well, workflow FROM workflow_type', conn)
    return df

@st.cache_data(ttl=CONFIG["CACHE_TTL"])
def load_delay_reasons_data():
    """Load delay reasons data."""
    conn = get_db_connection()
    df = pd.read_sql('SELECT well, process, reason, days, note, created_at FROM delay_reasons ORDER BY created_at DESC', conn)
    if df.empty:
        df = pd.DataFrame(columns=['well', 'process', 'reason', 'days', 'note', 'created_at'])
    return df

def write_to_db(well, process, start_date, end_date):
    """Write process data to database."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('REPLACE INTO process_data VALUES (?, ?, ?, ?)',
                  (well, process, start_date.isoformat() if start_date else None, 
                   end_date.isoformat() if end_date else None))
        conn.commit()
        st.cache_data.clear()  # Clear cache after write
    except Exception as e:
        st.error(f"Database error: {e}")

def write_workflow_to_db(well, workflow):
    """Write workflow type to database."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('REPLACE INTO workflow_type (well, workflow) VALUES (?, ?)', (well, workflow))
        conn.commit()
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Database error: {e}")

def write_delay_reason_to_db(well, process, reason, days, note):
    """Write delay reason to database."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO delay_reasons (well, process, reason, days, note, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                  (well, process, reason, days, note, datetime.now().isoformat()))
        conn.commit()
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Database error: {e}")

# ============================================================================
# AUTHENTICATION
# ============================================================================

def init_session_state():
    """Initialize session state variables."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'role' not in st.session_state:
        st.session_state.role = None

def authenticate():
    """Handle authentication via session state."""
    init_session_state()
    
    if not st.session_state.authenticated:
        st.sidebar.header("🔐 Authentication")
        username = st.sidebar.text_input("Username", key="auth_username")
        password = st.sidebar.text_input("Password", type="password", key="auth_password")
        
        if st.sidebar.button("Login"):
            if username in USERS and USERS[username] == password:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.role = USERS[username]
                st.rerun()
            else:
                st.sidebar.error("Invalid username or password")
        return False
    return True

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_current_process(df_well, processes):
    """
    Determine the current process for a well.
    Logic:
    1. First process with start_date set and end_date null
    2. If none, next process after the last one with end_date
    3. If nothing started, the first process
    """
    # Case 1: Any process has started but not finished
    in_progress = df_well[(df_well['start_date'].notna()) & (df_well['end_date'].isna())]
    if not in_progress.empty:
        return in_progress.iloc[0]['process']
    
    # Case 2: If no unfinished process, use next process after last completed
    completed = df_well[df_well['end_date'].notna()].sort_values(by='end_date')
    if not completed.empty:
        last_completed = completed.iloc[-1]['process']
        try:
            idx = processes.index(last_completed)
            if idx + 1 < len(processes):
                return processes[idx + 1]
        except ValueError:
            pass
    
    # Case 3: Nothing started yet → first process
    return processes[0] if len(processes) > 0 else None

def calculate_duration(start_date, end_date):
    """Calculate exact duration in days (can be 0 for same-day processes)."""
    if pd.isna(start_date) or pd.isna(end_date):
        return None
    return (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days

def get_status_color(elapsed_days, kpi_days):
    """Determine status color based on elapsed days vs KPI."""
    if kpi_days <= 0:
        return CONFIG["COLOR_ON_TRACK"]
    
    percentage = (elapsed_days / kpi_days) * 100
    if percentage <= 80:
        return CONFIG["COLOR_ON_TRACK"]
    elif percentage <= 100:
        return CONFIG["COLOR_AT_RISK"]
    else:
        return CONFIG["COLOR_OVERDUE"]

def get_status_text(elapsed_days, kpi_days):
    """Determine status text."""
    if kpi_days <= 0:
        return "On Track"
    
    percentage = (elapsed_days / kpi_days) * 100
    if percentage <= 80:
        return "On Track"
    elif percentage <= 100:
        return "At Risk"
    else:
        return "Overdue"

# ============================================================================
# MAIN APPLICATION
# ============================================================================

# Initialize database
init_db()

# Authenticate user
if not authenticate():
    st.stop()

st.sidebar.success(f"✓ Logged in as {st.session_state.username} ({st.session_state.role})")

# Load all data once
df_all_data = load_all_process_data()
df_workflows = load_workflow_data()
df_delays = load_delay_reasons_data()

# ============================================================================
# SIDEBAR: WELL SELECTION AND DATA ENTRY
# ============================================================================

st.sidebar.header("📊 Well Selection and Data Entry")
selected_well = st.sidebar.selectbox("Select a Well", WELLS)
st.session_state['selected_well'] = selected_well

# Get saved workflow
saved_workflow = df_workflows[df_workflows['well'] == selected_well]['workflow'].values
default_workflow = saved_workflow[0] if len(saved_workflow) > 0 else "HBF"

selected_workflow = st.sidebar.selectbox("Select Workflow", ["HBF", "HAF"], index=["HBF", "HAF"].index(default_workflow))
st.session_state["workflow_type"] = selected_workflow

# Update workflow if changed
if len(saved_workflow) == 0 or selected_workflow != saved_workflow[0]:
    write_workflow_to_db(selected_well, selected_workflow)

# Data entry for "entry" role
if st.session_state.role == "entry":
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📝 Process Dates")
    
    # Rig Release
    df_well_rig = df_all_data[(df_all_data['well'] == selected_well) & (df_all_data['process'] == "Rig Release")]
    default_rig_release = df_well_rig['start_date'].values[0] if not df_well_rig.empty and pd.notna(df_well_rig['start_date'].values[0]) else None
    
    rig_release_date = st.sidebar.date_input(
        "Rig Release",
        value=default_rig_release,
        key="rig_release_input"
    )
    
    if rig_release_date:
        write_to_db(selected_well, "Rig Release", rig_release_date, rig_release_date)
    
    # Rig Out
    df_well_rigout = df_all_data[(df_all_data['well'] == selected_well) & (df_all_data['process'] == "Rig Out")]
    default_rig_out = df_well_rigout['start_date'].values[0] if not df_well_rigout.empty and pd.notna(df_well_rigout['start_date'].values[0]) else None
    
    rig_out_date = st.sidebar.date_input(
        "Rig Out",
        value=default_rig_out,
        key="rig_out_input"
    )
    
    if rig_out_date:
        write_to_db(selected_well, "Rig Out", rig_out_date, rig_out_date)
    
    # Remaining processes
    for process in PROCESSES[1:]:
        st.sidebar.markdown(f"**{process}**")
        col_start, col_end = st.sidebar.columns(2)
        
        df_process = df_all_data[(df_all_data['well'] == selected_well) & (df_all_data['process'] == process)]
        default_start = df_process['start_date'].values[0] if not df_process.empty and pd.notna(df_process['start_date'].values[0]) else None
        default_end = df_process['end_date'].values[0] if not df_process.empty and pd.notna(df_process['end_date'].values[0]) else None
        
        with col_start:
            start_date = st.date_input(f"Start", value=default_start, key=f"start_{process}")
        
        with col_end:
            end_date = st.date_input(f"End", value=default_end, key=f"end_{process}")
        
        if start_date and end_date:
            if start_date > end_date:
                st.sidebar.error(f"Error: Start date must be before or equal to End date for {process}")
            else:
                write_to_db(selected_well, process, start_date, end_date)

# ============================================================================
# MAIN CONTENT AREA
# ============================================================================

# Reload data after potential writes
df_all_data = load_all_process_data()

# Filter data for selected well
df_well = df_all_data[df_all_data['well'] == selected_well].copy()

# Merge with full process list to preserve order
df_well_full = pd.DataFrame({'process': PROCESSES})
df_well = pd.merge(df_well_full, df_well, on='process', how='left')

# ============================================================================
# EXECUTIVE KPI CARDS (Top Row)
# ============================================================================

st.markdown(f"# 📊 Well: {selected_well} ({st.session_state['workflow_type']})")

# Calculate executive metrics
wells_on_stream = 0
total_cycle_time = 0
wells_on_target = 0
wells_at_risk = 0

for well in WELLS:
    df_w = df_all_data[df_all_data['well'] == well]
    
    # Check if well is on stream
    on_stream_row = df_w[df_w['process'] == 'On stream']
    if not on_stream_row.empty and pd.notna(on_stream_row['end_date'].values[0]):
        wells_on_stream += 1
    
    # Calculate cycle time (Rig Release to On Stream)
    rig_release_row = df_w[df_w['process'] == 'Rig Release']
    on_stream_row = df_w[df_w['process'] == 'On stream']
    
    if (not rig_release_row.empty and pd.notna(rig_release_row['start_date'].values[0]) and
        not on_stream_row.empty and pd.notna(on_stream_row['end_date'].values[0])):
        
        cycle_days = (pd.to_datetime(on_stream_row['end_date'].values[0]) - 
                      pd.to_datetime(rig_release_row['start_date'].values[0])).days
        total_cycle_time += cycle_days
        
        if cycle_days <= CONFIG["TOTAL_KPI_DAYS"]:
            wells_on_target += 1
        else:
            wells_at_risk += 1

avg_cycle_time = total_cycle_time / wells_on_stream if wells_on_stream > 0 else 0
pct_on_target = (wells_on_target / len(WELLS)) * 100 if len(WELLS) > 0 else 0

# Display KPI cards
col_card1, col_card2, col_card3, col_card4 = st.columns(4)

with col_card1:
    st.metric(label="Wells On Stream", value=wells_on_stream, delta=f"of {len(WELLS)}")

with col_card2:
    st.metric(label="Avg Cycle Time (days)", value=int(avg_cycle_time))

with col_card3:
    st.metric(label="% Wells On-Target", value=f"{pct_on_target:.1f}%")

with col_card4:
    st.metric(label="Wells At-Risk", value=wells_at_risk, delta=f"of {len(WELLS)}")

st.markdown("---")

# ============================================================================
# MAIN LAYOUT: 3 COLUMNS
# ============================================================================

col1, col2, col3 = st.columns((1.5, 8.0, 1.0), gap='medium')

# ============================================================================
# COLUMN 1: CURRENT PROCESS PANEL
# ============================================================================

with col1:
    st.subheader("Current Process")
    
    current_process = get_current_process(df_well, PROCESSES)
    
    if current_process:
        row = df_well[df_well['process'] == current_process].iloc[0]
        start_date = row['start_date']
        end_date = row['end_date']
        kpi_value = KPI_DICT.get(current_process, 1)
        
        # If start date is not set, use previous process's end date
        if pd.isna(start_date):
            prev_idx = PROCESSES.index(current_process) - 1
            if prev_idx >= 0:
                prev_process = PROCESSES[prev_idx]
                prev_row = df_well[df_well['process'] == prev_process]
                if not prev_row.empty and pd.notna(prev_row['end_date'].values[0]):
                    start_date = prev_row['end_date'].values[0]
        
        if pd.notna(start_date):
            elapsed_days = (date.today() - start_date.date()).days
            remaining_days = max(kpi_value - elapsed_days, 0) if kpi_value > 0 else 0
            pct_consumed = round((elapsed_days / kpi_value) * 100, 1) if kpi_value > 0 else 0
            projected_end = start_date + timedelta(days=kpi_value) if kpi_value > 0 else None
            status = get_status_text(elapsed_days, kpi_value)
            status_color = get_status_color(elapsed_days, kpi_value)
        else:
            elapsed_days = 0
            remaining_days = kpi_value if kpi_value > 0 else 0
            pct_consumed = 0
            projected_end = None
            status = "Not Started"
            status_color = CONFIG["COLOR_ON_TRACK"]
        
        st.write(f"**Process:** {current_process}")
        st.write(f"**Start Date:** {start_date.date() if pd.notna(start_date) else 'Not set'}")
        st.write(f"**Days Elapsed:** {elapsed_days}")
        st.write(f"**KPI (days):** {kpi_value}")
        st.write(f"**Days Remaining:** {remaining_days}")
        st.write(f"**% of KPI Consumed:** {pct_consumed}%")
        st.write(f"**Projected End:** {projected_end.date() if projected_end else 'N/A'}")
        
        # Status indicator
        st.markdown(f"### Status: <span style='color: {status_color}; font-weight: bold;'>{status}</span>", unsafe_allow_html=True)
        
        # Progress bar
        progress = min(elapsed_days / kpi_value, 1.0) if kpi_value > 0 else 0
        st.progress(progress)
    else:
        st.write("No processes defined.")
    
    # Process summary list
    st.markdown("---")
    st.subheader("Process Summary")
    
    for process in PROCESSES[1:]:
        row = df_well[df_well['process'] == process]
        if not row.empty:
            start = row['start_date'].values[0]
            end = row['end_date'].values[0]
            
            if pd.notna(start) and pd.notna(end):
                duration = calculate_duration(start, end)
                kpi = KPI_DICT.get(process, '-')
                st.write(f"**{process}:** {duration} days (KPI: {kpi})")
            else:
                st.write(f"**{process}:** Pending")

# ============================================================================
# COLUMN 2: VISUALIZATIONS
# ============================================================================

with col2:
    # Gauge chart for current process
    if current_process and pd.notna(start_date):
        st.subheader("Current Process: Days vs KPI")
        
        kpi_val = KPI_DICT.get(current_process, 1)
        if kpi_val <= 0:
            kpi_val = 1
        
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=elapsed_days,
            title={'text': f"{current_process}"},
            delta={'reference': kpi_val},
            gauge={
                'axis': {'range': [None, max(kpi_val * 1.3, elapsed_days + 10)]},
                'bar': {'color': status_color},
                'steps': [
                    {'range': [0, kpi_val * 0.8], 'color': CONFIG["COLOR_ON_TRACK"]},
                    {'range': [kpi_val * 0.8, kpi_val], 'color': CONFIG["COLOR_AT_RISK"]},
                    {'range': [kpi_val, max(kpi_val * 1.3, elapsed_days + 10)], 'color': CONFIG["COLOR_OVERDUE"]}
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 4},
                    'thickness': 0.75,
                    'value': kpi_val
                }
            }
        ))
        
        fig_gauge.update_layout(height=350)
        st.plotly_chart(fig_gauge, use_container_width=True)
    
    # Gantt timeline
    st.subheader("Process Timeline (Gantt)")
    
    gantt_data = []
    for process in PROCESSES:
        row = df_well[df_well['process'] == process]
        if not row.empty and pd.notna(row['start_date'].values[0]):
            start = row['start_date'].values[0]
            end = row['end_date'].values[0] if pd.notna(row['end_date'].values[0]) else date.today()
            
            kpi = KPI_DICT.get(process, 1)
            status = get_status_text(calculate_duration(start, end), kpi) if pd.notna(row['end_date'].values[0]) else "In Progress"
            
            gantt_data.append({
                'Task': process,
                'Start': start,
                'Finish': end,
                'Status': status
            })
    
    if gantt_data:
        df_gantt = pd.DataFrame(gantt_data)
        
        # Color mapping
        color_map = {
            'On Track': CONFIG["COLOR_ON_TRACK"],
            'At Risk': CONFIG["COLOR_AT_RISK"],
            'Overdue': CONFIG["COLOR_OVERDUE"],
            'In Progress': '#3498db'
        }
        
        fig_gantt = px.timeline(
            df_gantt,
            x_start='Start',
            x_end='Finish',
            y='Task',
            color='Status',
            color_discrete_map=color_map,
            title="Well Process Timeline"
        )
        
        # Add today line
        fig_gantt.add_vline(x=date.today(), line_dash="dash", line_color="red", annotation_text="Today")
        fig_gantt.update_layout(height=400)
        st.plotly_chart(fig_gantt, use_container_width=True)
    
    # Main grouped bar chart with KPI line and variance toggle
    st.subheader("Process Duration vs KPI")
    
    chart_data = []
    for process in PROCESSES[1:]:
        row = df_well[df_well['process'] == process]
        if not row.empty and pd.notna(row['start_date'].values[0]) and pd.notna(row['end_date'].values[0]):
            duration = calculate_duration(row['start_date'].values[0], row['end_date'].values[0])
            kpi = KPI_DICT.get(process, 0)
            variance = duration - kpi
            
            chart_data.append({
                'Process': process,
                'Actual Days': duration,
                'KPI Days': kpi,
                'Variance': variance
            })
    
    if chart_data:
        df_chart = pd.DataFrame(chart_data)
        
        # Toggle for variance view
        chart_type = st.radio("Chart Type:", ["Actual vs KPI", "Variance"], horizontal=True)
        
        if chart_type == "Actual vs KPI":
            fig_bar = go.Figure()
            
            fig_bar.add_trace(go.Bar(
                x=df_chart['Process'],
                y=df_chart['Actual Days'],
                name='Actual Days',
                marker_color='#3498db'
            ))
            
            fig_bar.add_trace(go.Scatter(
                x=df_chart['Process'],
                y=df_chart['KPI Days'],
                mode='lines+markers',
                name='KPI Target',
                line=dict(color='red', dash='dash', width=3),
                marker=dict(size=8)
            ))
            
            # Add shaded KPI band
            fig_bar.add_hrect(
                y0=0, y1=df_chart['KPI Days'].max() * 1.1,
                fillcolor="green", opacity=0.1,
                layer="below", line_width=0,
            )
            
            # Add delta labels
            for idx, row in df_chart.iterrows():
                delta = row['Actual Days'] - row['KPI Days']
                color = 'green' if delta <= 0 else 'red'
                fig_bar.add_annotation(
                    x=row['Process'],
                    y=row['Actual Days'],
                    text=f"{delta:+.0f}",
                    showarrow=True,
                    arrowhead=2,
                    font=dict(color=color, size=10)
                )
        else:
            # Diverging variance bar
            colors = [CONFIG["COLOR_ON_TRACK"] if v <= 0 else CONFIG["COLOR_OVERDUE"] for v in df_chart['Variance']]
            
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=df_chart['Variance'],
                y=df_chart['Process'],
                orientation='h',
                marker_color=colors,
                text=df_chart['Variance'],
                textposition='auto'
            ))
            
            fig_bar.add_vline(x=0, line_dash="dash", line_color="black")
        
        fig_bar.update_layout(
            title="Process Performance vs KPI",
            xaxis_title="Days" if chart_type == "Actual vs KPI" else "Variance (Days)",
            yaxis_title="Process" if chart_type == "Variance" else "",
            height=400,
            hovermode='closest'
        )
        
        st.plotly_chart(fig_bar, use_container_width=True)

# ============================================================================
# COLUMN 3: GAP ANALYSIS WITH DELAY REASONS
# ============================================================================

with col3:
    st.subheader("Gap Analysis")
    
    gap_analysis_data = []
    
    for well in WELLS:
        df_w = df_all_data[df_all_data['well'] == well]
        
        # Get Rig Release and On stream dates
        rig_row = df_w[df_w['process'] == 'Rig Release']
        ons_row = df_w[df_w['process'] == 'On stream']
        
        if (not rig_row.empty and pd.notna(rig_row['start_date'].values[0]) and
            not ons_row.empty and pd.notna(ons_row['end_date'].values[0])):
            
            total_days = (pd.to_datetime(ons_row['end_date'].values[0]) - 
                         pd.to_datetime(rig_row['start_date'].values[0])).days
            gap = total_days - CONFIG["TOTAL_KPI_DAYS"]
            
            # Get delay reasons for this well
            delay_rows = df_delays[df_delays['well'] == well]
            top_reason = delay_rows.iloc[0]['reason'] if not delay_rows.empty else "N/A"
            days_attributed = delay_rows.iloc[0]['days'] if not delay_rows.empty else 0
            
            gap_analysis_data.append({
                'Well': well,
                'Total Gap (days)': gap,
                'Status': 'Over' if gap > 0 else 'Under',
                'Top Reason': top_reason,
                'Days Attributed': days_attributed
            })
        else:
            gap_analysis_data.append({
                'Well': well,
                'Total Gap (days)': None,
                'Status': 'Incomplete',
                'Top Reason': 'N/A',
                'Days Attributed': 0
            })
    
    df_gap = pd.DataFrame(gap_analysis_data)
    st.dataframe(df_gap, use_container_width=True, hide_index=True)
    
    # Form to add delay reasons (only for entry role)
    if st.session_state.role == "entry":
        st.markdown("---")
        st.subheader("Add Delay Reason")
        
        with st.form("delay_reason_form"):
            reason_well = st.selectbox("Well", WELLS, key="delay_well")
            reason_process = st.selectbox("Process", PROCESSES, key="delay_process")
            reason_category = st.selectbox("Reason Category", DELAY_REASONS, key="delay_reason")
            reason_days = st.number_input("Days Attributed", min_value=0, max_value=365, key="delay_days")
            reason_note = st.text_area("Note", key="delay_note")
            
            if st.form_submit_button("Add Delay Reason"):
                write_delay_reason_to_db(reason_well, reason_process, reason_category, reason_days, reason_note)
                st.success("Delay reason added!")
                st.rerun()

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
st.markdown(f"**Dashboard Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.markdown("*Optimized for Executive Stakeholders | Refactored for Performance and Clarity*")
