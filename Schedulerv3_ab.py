import pulp
import pandas as pd
from datetime import datetime
import json

################ JSON saving now ########################

def load_db():
    try:
        with open("agents_db.json", "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_db(agents_db):
    with open("agents_db.json", "w") as file:
        json.dump(agents_db, file)

def add_agent(agents_list, agent_id, name, type_fte, FTE, days_worked, hours_worked): #NO PROTECTION IF AGENT EXISTS OR ENTRY ISN'T A NUMBER for FTE, etc.
    agents_list.append({"Agent ID": agent_id,"name": name,"type": type_fte, "FTE": FTE, "days-worked":days_worked,"Hours-worked":hours_worked})


# --- 1. CONFIGURATION ---
agents_db = load_db()  # Load existing agents from JSON, or start fresh
#print(agents_db)
#add_agent(agents_db, "Agent_01", "Agathe", "FT", 1, [0,1,2,3,4], (8,18))
#add_agent(agents_db, "Agent_02", "Simon", "FT", 1, [0,1,2,3,4], (8,18))
#save_db(agents_db)
#print(agents_db)
#input("Want more agents?")
#for i in range(1, 51):
#    if i <= 25: 
#        agents_db[f"Agent_{i:02d}"] = {"type": "FT", "workdays": [0,1,2,3,4], "window": (8, 16)}
#    elif i <= 15: 
#        agents_db[f"Agent_{i:02d}"] = {"type": "FT", "workdays": [0,1,2,3,4], "window": (16, 0)}
#    else: 
#        agents_db[f"Agent_{i:02d}"] = {"type": "PT", "workdays": [0,1,2,3,4], "window": (0, 8)}

def solve_full_period(clean_df):
    all_dates = sorted(clean_df['Date'].unique())
    prob = pulp.LpProblem("Global_Schedule", pulp.LpMinimize)
    
    choices = {}      # (agent, date, start_hour)
    slack_vars = {}   # (date, hour)
    agent_daily_work = {} # (agent, date) -> Binary (1 if working that day)

    # --- 2. VARIABLE CREATION ---
    for d in all_dates:
        ts = pd.to_datetime(d)
        weekday = ts.weekday()
        avail_today = [a for a, info in agents_db.items() if weekday in info['workdays']]
        
        for a in avail_today:
            s_min, s_max = agents_db[a]['Hours-worked']
            # Track if agent works at all on this day
            agent_daily_work[(a, d)] = pulp.LpVariable(f"Work_{a}_{d}", cat="Binary")
            
            day_choices = []
            for s in range(s_min, s_max + 1):
                v = pulp.LpVariable(f"S_{a}_{d}_{s}", cat="Binary")
                choices[(a, d, s)] = v
                day_choices.append(v)
            
            # Constraint: Max 1 shift per day
            prob += pulp.lpSum(day_choices) == agent_daily_work[(a, d)]

    # --- 3. COVERAGE & SLACK ---
    for d in all_dates:
        day_data = clean_df[clean_df['Date'] == d]
        demand_dict = dict(zip(day_data['Hour'], day_data['FTE_Brut']))
        
        for h in range(24):
            coverage = []
            for (a, date, s), var in choices.items():
                if date == d:
                    dur = 8 if agents_db[a]['type'] == "FT" else 4
                    if s <= h < s + dur:
                        # Handle Lunch for FT
                        if agents_db[a]['type'] == "FT" and h == (s + 4):
                            continue
                        coverage.append(var)
            
            slack = pulp.LpVariable(f"Slack_{d}_{h}", lowBound=0)
            slack_vars[(d, h)] = slack
            prob += pulp.lpSum(coverage) + slack >= demand_dict.get(h, 0)

    # --- 4. LAYER: EQUITY (Rebalancing) ---
    # Target: Total shifts needed / Number of agents
    total_days = len(all_dates)
    for a in agents_db:
        # Number of shifts assigned to this agent over the period
        agent_total_shifts = pulp.lpSum([agent_daily_work[(a, d)] for d in all_dates if (a, d) in agent_daily_work])
        
        # Helper variables to measure deviation from a "fair" load
        # We penalize agents working way more or way less than 4 shifts a week (as an example)
        over_work = pulp.LpVariable(f"Over_{a}", lowBound=0)
        prob += agent_total_shifts <= 5 + over_work # Penalty if more than 5 shifts/week

    # --- 5. LAYER: NO 3-DAY GAPS ---
    # For every agent, in any rolling 3-day window they are available, they must work >= 1 day
    for a in agents_db:
        workdays = agents_db[a]['workdays']
        for i in range(len(all_dates) - 2):
            window = all_dates[i:i+3]
            # Only apply if the agent is actually contracted to work these days
            valid_days_in_window = [d for d in window if pd.to_datetime(d).weekday() in workdays]
            
            if len(valid_days_in_window) == 3:
                prob += pulp.lpSum([agent_daily_work[(a, d)] for d in valid_days_in_window]) >= 1

    # --- 6. OBJECTIVE ---
    # 1. Minimize Understaffing (Slack) - Priority 1
    # 2. Minimize Total Agents used - Priority 2
    # 3. Minimize Overwork - Priority 3
    prob += (
        pulp.lpSum(slack_vars.values()) * 100 + 
        pulp.lpSum(choices.values()) * 1 +
        pulp.lpSum([pulp.LpVariable(f"dev_{a}") for a in agents_db]) * 10
    )

    print("Solving Global Schedule (this may take a moment)...")
    prob.solve(pulp.PULP_CBC_CMD(msg=1, timeLimit=240))
    
    # --- 7. RESULTS ---
    res = []
    for (a, d, s), var in choices.items():
        if pulp.value(var) == 1:
            dur = 8 if agents_db[a]['type'] == "FT" else 4
            res.append({
                "Date": pd.to_datetime(d).date(),
                "Agent": a,
                "Start": f"{s:02d}:00",
                "End": f"{(s+dur)%24:02d}:00"
            })
    return res

# --- MAIN EXECUTION ---
try:
    df = pd.read_excel("need.xlsx")
    clean_df = pd.DataFrame()
    clean_df['Date'] = pd.to_datetime(df.iloc[:, 0])
    clean_df['Hour'] = pd.to_numeric(df.iloc[:, 2].astype(str).str.split(':').str[0], errors='coerce')
    clean_df['FTE_Brut'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
    clean_df = clean_df.dropna(subset=['Hour'])

    final_results = solve_full_period(clean_df)

    if final_results:
        output_df = pd.DataFrame(final_results)
        output_df.to_excel("final_schedule_global.xlsx", index=False)
        print(f"\n*** SUCCESS! {len(final_results)} assignments made. ***")
    else:
        print("\n*** ERROR: No assignments generated. ***")

except Exception:
    import traceback
    print(traceback.format_exc())