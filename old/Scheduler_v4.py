import pulp
import pandas as pd
from datetime import datetime
import json

# ============================================================
# JSON HELPERS
# ============================================================

def load_db():
    try:
        with open("agents_db.json", "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_db(agents_db):
    with open("agents_db.json", "w") as file:
        json.dump(agents_db, file)

def add_agent(agents_list, agent_id, name, type_fte, FTE, days_worked, hours_worked):
    agents_list.append({
        "Agent ID": agent_id,
        "name": name,
        "type": type_fte,
        "FTE": FTE,
        "days-worked": days_worked,
        "Hours-worked": hours_worked
    })

# ============================================================
# LOAD AGENTS
# ============================================================

agents_db = load_db()

# Deduplicate by Agent ID (keeps first occurrence)
seen = set()
agents_db_clean = []
for agent in agents_db:
    if agent["Agent ID"] not in seen:
        seen.add(agent["Agent ID"])
        agents_db_clean.append(agent)

# Build a lookup dict for easy access: {"Agent_01": {...}, ...}
agents_dict = {agent["Agent ID"]: agent for agent in agents_db_clean}

print(f"Loaded {len(agents_dict)} agents: {list(agents_dict.keys())}")

# ============================================================
# SOLVER
# ============================================================

def solve_full_period(clean_df):
    all_dates = sorted(clean_df['Date'].unique())
    prob = pulp.LpProblem("Global_Schedule", pulp.LpMinimize)

    choices = {}           # (agent_id, date, start_hour) -> LpVariable
    slack_vars = {}        # (date, hour) -> LpVariable
    agent_daily_work = {}  # (agent_id, date) -> LpVariable (Binary)

    # --- 2. VARIABLE CREATION ---
    for d in all_dates:
        weekday = pd.to_datetime(d).weekday()

        # ✅ FIX: iterate over dict items (agent_id, agent_info)
        avail_today = [
            agent_id for agent_id, info in agents_dict.items()
            if weekday in info['days-worked']  # ✅ FIX: 'days-worked' not 'workdays'
        ]

        for a in avail_today:
            info = agents_dict[a]
            s_min, s_max = info['Hours-worked']

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
                    agent_type = agents_dict[a]['type']  # ✅ FIX: use agents_dict
                    dur = 8 if agent_type == "FT" else 4
                    if s <= h < s + dur:
                        if agent_type == "FT" and h == (s + 4):
                            continue
                        coverage.append(var)

            slack = pulp.LpVariable(f"Slack_{d}_{h}", lowBound=0)
            slack_vars[(d, h)] = slack
            prob += pulp.lpSum(coverage) + slack >= demand_dict.get(h, 0)

    # --- 4. EQUITY (Max shifts per period) ---
    over_work_vars = {}
    for a in agents_dict:  # ✅ FIX: iterate over agents_dict
        agent_total_shifts = pulp.lpSum([
            agent_daily_work[(a, d)]
            for d in all_dates
            if (a, d) in agent_daily_work
        ])
        over_work = pulp.LpVariable(f"Over_{a}", lowBound=0)
        over_work_vars[a] = over_work
        prob += agent_total_shifts <= 5 + over_work

    # --- 5. NO 3-DAY GAPS ---
    for a, info in agents_dict.items():  # ✅ FIX: use agents_dict
        workdays = info['days-worked']   # ✅ FIX: 'days-worked' not 'workdays'
        for i in range(len(all_dates) - 2):
            window = all_dates[i:i+3]
            valid_days = [
                d for d in window
                if pd.to_datetime(d).weekday() in workdays
            ]
            if len(valid_days) == 3:
                prob += pulp.lpSum([
                    agent_daily_work[(a, d)]
                    for d in valid_days
                    if (a, d) in agent_daily_work
                ]) >= 1

    # --- 6. OBJECTIVE ---
    prob += (
        pulp.lpSum(slack_vars.values()) * 100 +
        pulp.lpSum(choices.values()) * 1 +
        pulp.lpSum(over_work_vars.values()) * 10  # ✅ FIX: use actual variables
    )

    print("Solving... (time limit: 240s)")
    prob.solve(pulp.PULP_CBC_CMD(msg=1, timeLimit=240))

    # --- 7. RESULTS ---
    res = []
    for (a, d, s), var in choices.items():
        if pulp.value(var) == 1:
            dur = 8 if agents_dict[a]['type'] == "FT" else 4  # ✅ FIX
            res.append({
                "Date": pd.to_datetime(d).date(),
                "Agent": agents_dict[a]['name'],  # ✅ BONUS: show name, not ID
                "Agent ID": a,
                "Start": f"{s:02d}:00",
                "End": f"{(s + dur) % 24:02d}:00"
            })
    return res

# ============================================================
# MAIN
# ============================================================
try:
    df = pd.read_excel("need.xlsx")
    clean_df = pd.DataFrame()
    clean_df['Date'] = pd.to_datetime(df.iloc[:, 0])
    clean_df['Hour'] = pd.to_numeric(
        df.iloc[:, 2].astype(str).str.split(':').str[0], errors='coerce'
    )
    clean_df['FTE_Brut'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
    clean_df = clean_df.dropna(subset=['Hour'])

    final_results = solve_full_period(clean_df)

    if final_results:
        output_df = pd.DataFrame(final_results)
        output_df.to_excel("final_schedule_global.xlsx", index=False)
        print(f"\n✅ SUCCESS! {len(final_results)} assignments made.")
    else:
        print("\n❌ ERROR: No assignments generated.")

except Exception:
    import traceback
    print(traceback.format_exc())
