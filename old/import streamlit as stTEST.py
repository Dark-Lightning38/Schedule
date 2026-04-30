import streamlit as st
import pandas as pd
from streamlit_apexcharts import streamlit_apexcharts

st.set_page_config(layout="wide") # Use the whole screen!

# Load the results from your once-a-month run @st.cache_data def load_data():
    df = pd.read_csv("final_schedule.csv")
    df['Date'] = pd.to_datetime(df['Date'])
    return df

df = load_data()

# --- SIDEBAR FILTERS ---
with st.sidebar:
    st.header("Planning Filters")
    # Let them pick which week of the 3-month period to view
    all_weeks = df['Date'].dt.strftime('%Y-W%U').unique()
    selected_week = st.selectbox("Select Week", all_weeks)

# Filter data for that week
week_df = df[df['Date'].dt.strftime('%Y-W%U') == selected_week]

# --- MAIN DISPLAY ---
st.title(f"Contact Centre Schedule: {selected_week}")

# Format data for ApexCharts Heatmap
# We need: x = Days, y = Agents, value = Shift Code (1 for Early, 2 for Late, etc.) series = [] for agent in week_df['Agent'].unique():
    agent_data = week_df[week_df['Agent'] == agent]
    series.append({
        "name": agent,
        "data": [{"x": d.strftime('%a %d'), "y": s} for d, s in zip(agent_data['Date'], agent_data['ShiftValue'])]
    })

options = {
    "chart": {"type": "heatmap", "height": 600},
    "dataLabels": {"enabled": False},
    "colors": ["#008FFB"], # You can customize colors based on shift type
    "title": {"text": "Agent Daily Allocation"} }

streamlit_apexcharts(options=options, series=series)
