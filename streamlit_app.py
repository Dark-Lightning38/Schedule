import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import calendar

st.set_page_config(page_title="Work Shift Scheduler", layout="wide")

st.title("📅 Work Shift Scheduler")
if 'shifts' not in st.session_state:
    st.session_state.shifts = pd.DataFrame(columns=['Date', 'Matricule', 'Person', 'Shift', 'Status'])

# Sidebar for adding shifts
with st.sidebar:
    st.header("➕ Add New Shift")
    
    # Future dates only
    default_start = datetime.now().date() + timedelta(days=1)
    default_end = default_start + timedelta(days=7)
    
    st.write("**Select Date Range:**")
    shift_date_range = st.date_input(
        "Start and End Date",
        value=(default_start, default_end),
        min_value=default_start,
        key="date_range"
    )
    
    st.write("**Employee Details:**")
    matricule = st.text_input("Employee Matricule")
    person_name = st.text_input("Employee Name")
    
    st.write("**Shift Information:**")
    shift_type = st.selectbox("Shift Type", ["Morning (6AM-2PM)", "Afternoon (2PM-10PM)", "Night (10PM-6AM)"])
    status = st.selectbox("Status", ["Scheduled - WFM", "Scheduled - Confirmed", "Requested for Cancellation", "Cancelled"])
    
    if st.button("➕ Add Shift", use_container_width=True):
        if not person_name.strip():
            st.warning("Employee Name cannot be empty.")
        elif not matricule.strip():
            st.warning("Employee Matricule cannot be empty.")
        else:
            # Determine start/end (support single date or range)
            if isinstance(shift_date_range, tuple):
                start_date, end_date = shift_date_range
            else:
                start_date = end_date = shift_date_range

            dates = pd.date_range(start=start_date, end=end_date).date
            added_count = 0

            for date in dates:
                duplicate = (
                    (pd.to_datetime(st.session_state.shifts['Date']).dt.date == date) &
                    (st.session_state.shifts['Matricule'].str.lower() == matricule.strip().lower())
                ).any()
                if duplicate:
                    continue

                new_shift = pd.DataFrame({
                    'Date': [date],
                    'Matricule': [matricule.strip()],
                    'Person': [person_name.strip()],
                    'Shift': [shift_type],
                    'Status': [status]
                })
                st.session_state.shifts = pd.concat([st.session_state.shifts, new_shift], ignore_index=True)
                added_count += 1

            if added_count == 0:
                st.warning("A shift for this employee on these date(s) already exists.")
            else:
                st.success(f"✅ {added_count} shift(s) added!")

# Filter section
st.subheader("🔍 Filter Schedule")
if not st.session_state.shifts.empty:
    all_persons = sorted(st.session_state.shifts['Person'].unique().tolist())
    selected_persons = st.multiselect(
        "Select Employee(s)",
        options=all_persons,
        default=all_persons,
        key="person_filter"
    )
    filtered_shifts = st.session_state.shifts[st.session_state.shifts['Person'].isin(selected_persons)]
else:
    filtered_shifts = st.session_state.shifts
    selected_persons = []

# Stats section
st.subheader("📈 Statistics")
col_stat1, col_stat2, col_stat3 = st.columns(3)

with col_stat1:
    if not filtered_shifts.empty:
        st.metric("Total Shifts", len(filtered_shifts))
    else:
        st.metric("Total Shifts", 0)

with col_stat2:
    if not filtered_shifts.empty:
        st.metric("Employees", filtered_shifts['Person'].nunique())
    else:
        st.metric("Employees", 0)

with col_stat3:
    if not filtered_shifts.empty:
        confirmed = len(filtered_shifts[filtered_shifts['Status'] == "Scheduled - Confirmed"])
        st.metric("Confirmed", confirmed)
    else:
        st.metric("Confirmed", 0)

# Main display - Table
st.subheader("📋 Schedule")
if not filtered_shifts.empty:
    # Make dataframe editable
    edited_df = st.data_editor(filtered_shifts, use_container_width=True, key="shift_editor", num_rows="dynamic")
    # Update session state with edited data
    if not edited_df.equals(filtered_shifts):
        st.session_state.shifts = st.session_state.shifts.drop(filtered_shifts.index)
        st.session_state.shifts = pd.concat([st.session_state.shifts, edited_df], ignore_index=True)
else:
    st.info("No shifts scheduled yet")

# Calendar view
st.subheader("📅 Calendar View")
if not filtered_shifts.empty:
    filtered_shifts_copy = filtered_shifts.copy()
    filtered_shifts_copy['Date'] = pd.to_datetime(filtered_shifts_copy['Date'])
    
    # Get date range
    min_date = filtered_shifts_copy['Date'].min().date()
    max_date = filtered_shifts_copy['Date'].max().date()
    
    # Create color mapping
    color_map = {
        "Morning (6AM-2PM)": "🔵",
        "Afternoon (2PM-10PM)": "🟠",
        "Night (10PM-6AM)": "🟢"
    }
    
    status_map = {
        "Scheduled - WFM": " (WFM)",
        "Scheduled - Confirmed": " ✓",
        "Requested for Cancellation": " ❌",
        "Cancelled": " ✗"
    }
    
    # Group by person and date
    calendar_data = {}
    for person in filtered_shifts_copy['Person'].unique():
        person_shifts = filtered_shifts_copy[filtered_shifts_copy['Person'] == person]
        calendar_data[person] = {}
        for idx, row in person_shifts.iterrows():
            date_key = row['Date'].date()
            shift_info = f"{color_map.get(row['Shift'], '⚪')}{status_map.get(row['Status'], '')}"
            if date_key not in calendar_data[person]:
                calendar_data[person][date_key] = []
            calendar_data[person][date_key].append(shift_info)
    
    # Display calendar table
    all_dates = pd.date_range(start=min_date, end=max_date).date
    
    calendar_df = pd.DataFrame(index=sorted(calendar_data.keys()))
    for date in all_dates:
        calendar_df[date.strftime('%a %m-%d')] = ""
    
    for person in calendar_df.index:
        for date in all_dates:
            if date in calendar_data[person]:
                calendar_df.loc[person, date.strftime('%a %m-%d')] = " ".join(calendar_data[person][date])
    
    st.dataframe(calendar_df, use_container_width=True)
    
    st.caption("🔵 = Morning | 🟠 = Afternoon | 🟢 = Night | ✓ = Confirmed | ❌ = Requested Cancel | ✗ = Cancelled")
else:
    st.info("No shifts to display in calendar")

# Clear all shifts button
if st.button("🗑️ Clear All Shifts", use_container_width=True):
    st.session_state.shifts = pd.DataFrame(columns=['Date', 'Matricule', 'Person', 'Shift', 'Status'])
    st.rerun()

