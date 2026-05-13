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

agents_db = load_db()

for i in range(1, 41):
   if i <= 22: 
       agents_db.append({
            "Agent ID": f"Agent_{i:02d}",
            "name": f"Name {i:02d}",
            "type": "FT",
            "FTE": 1.0,
            "days-worked": [0, 1, 2, 3, 4],
            "Hours-worked": (8, 16)
       })
   elif i <= 11: 
       agents_db.append({
            "Agent ID": f"Agent_{i:02d}",
            "name": f"Name {i:02d}",
            "type": "FT",
            "FTE": 1.0,
            "days-worked": [0, 1, 2, 3, 4],
            "Hours-worked": (16, 0)
       })
   else: 
       agents_db.append({
            "Agent ID": f"Agent_{i:02d}",
            "name": f"Name {i:02d}",
            "type": "PT",
            "FTE": 1.0,
            "days-worked": [0, 1, 2, 3, 4],
            "Hours-worked": (0, 8)
       })

save_db(agents_db)
