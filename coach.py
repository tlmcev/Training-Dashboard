import requests
import os
import json
from datetime import datetime, timedelta
import re  # Moved to top for cleanliness

# --- 1. SETUP & SECRETS ---
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

def get_strava_access_token():
    url = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': REFRESH_TOKEN,
        'grant_type': 'refresh_token'
    }
    response = requests.post(url, data=payload)
    return response.json().get('access_token')

def get_activities(access_token):
    two_weeks_ago = int((datetime.now() - timedelta(days=14)).timestamp())
    url = f"https://www.strava.com/api/v3/athlete/activities?after={two_weeks_ago}"
    headers = {'Authorization': f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    data = response.json()
    if isinstance(data, dict) and 'errors' in data:
        print(f"STRAVA API ERROR: {data}")
        exit(1)
    return data

def generate_activity_table(activities_list):
    # These are the headers for the Markdown table
    output_rows = [
        "| Workout | Distance | Date |",
        "| :--- | :--- | :--- |"
    ]
    
    # If the list is empty, we show a message instead of a blank table
    if not activities_list:
        return "No recent runs found. Time to hit the road!"

    for workout in activities_list[:5]:
        # IMPORTANT: These keys MUST match your Section 2 dictionary
        name = workout.get('name', 'Unknown')
        dist = f"{workout.get('distance_miles', 0)} mi"
        
        # We take the first 10 characters (YYYY-MM-DD)
        raw_date = workout.get('date', '0000-00-00')
        formatted_date = raw_date[:10]
        
        row = f"| {name} | {dist} | {formatted_date} |"
        output_rows.append(row)
        
    return "\n".join(output_rows)
    
# --- 2. DATA ACQUISITION ---
access_token = get_strava_access_token()
activities = get_activities(access_token)

# Process and Filter: Only Runs, sorted by date
formatted_activities = []
for act in activities:
    # Strava sometimes uses 'type' and sometimes 'sport_type'
    if act.get('type') == 'Run' or act.get('sport_type') == 'Run':
        formatted_activities.append({
            "name": act.get('name'),
            "date": act.get('start_date_local'),
            "distance_miles": round(act.get('distance', 0) / 1609.34, 2)
        })

# Sort by date (newest first) and take the top 3 for the dashboard
formatted_activities.sort(key=lambda x: x['date'], reverse=True)
recent_runs = formatted_activities[:3]

print(f"Successfully processed {len(recent_runs)} runs for the table.")


# --- 3. THE INTELLIGENCE STEP ---
current_time = datetime.now().strftime("%A, %b %d")
marathon_date = "November 1, 2026"

prompt = f"""
Today is {current_time}. 
Goal: NYC Marathon on {marathon_date}.
Plan: Hal Higdon Novice 2.

Strava Data (Last 14 Days of Runs): {json.dumps(formatted_activities)}

Mission:
- Analysis: Look at my recent runs. How is my pace and consistency?
- Next Week: Based on today's date, what are my specific mileage goals for the next 7 days?
- Full Schedule: Provide the full 18-week Hal Higdon Novice 2 table for my reference.
"""

# Using v1beta to ensure compatibility with the Flash model
gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
payload = {"contents": [{"parts": [{"text": prompt}]}]}

# 1. ATTEMPT AI ADVICE
try:
    response = requests.post(gemini_url, json=payload)
    if response.status_code == 200:
        result = response.json()
        advice = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')
        if advice:
            with open("latest_advice.txt", "w") as f:
                f.write(advice)
            print("SUCCESS: AI coaching advice updated.")
    else:
        print(f"AI Error {response.status_code}: {response.text}")
except Exception as e:
    print(f"AI Request Failed: {e}")

# 2. ALWAYS UPDATE THE DASHBOARD (Independent of AI)
try:
    # Generate the table string
    my_workout_table = generate_activity_table(recent_runs) 

    # --- ADD THE SCHEDULE HERE ---
    novice_2_plan = """
| Week | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Rest | 3m run | 3m run | 3m run | Rest | 4m run | Cross |
| 2 | Rest | 3m run | 3m run | 3m run | Rest | 5m run | Cross |
| 3 | Rest | 3m run | 3m run | 3m run | Rest | 6m run | Cross |
| 4 | Rest | 3m run | 4m run | 3m run | Rest | 7m run | Cross |
| 5 | Rest | 3m run | 4m run | 3m run | Rest | 8m run | Cross |
| 6 | Rest | 3m run | 4m run | 3m run | Rest | 9m run | Cross |
| 7 | Rest | 3m run | 5m run | 3m run | Rest | 10m run | Cross |
| 8 | Rest | 3m run | 5m run | 3m run | Rest | 11m run | Cross |
| 9 | Rest | 3m run | 5m run | 3m run | Rest | 12m run | Cross |
| 10 | Rest | 3m run | 5m run | 3m run | Rest | 13m run | Cross |
| 11 | Rest | 3m run | 6m run | 3m run | Rest | 14m run | Cross |
| 12 | Rest | 3m run | 6m run | 3m run | Rest | 15m run | Cross |
| 13 | Rest | 3m run | 6m run | 3m run | Rest | 16m run | Cross |
| 14 | Rest | 3m run | 7m run | 3m run | Rest | 17m run | Cross |
| 15 | Rest | 3m run | 7m run | 3m run | Rest | 18m run | Cross |
| 16 | Rest | 3m run | 8m run | 3m run | Rest | 19m run | Cross |
| 17 | Rest | 3m run | 4m run | 2m run | Rest | 8m run | Cross |
| 18 | Rest | 3m run | 2m run | Rest | Rest | 2m run | **NYC Marathon** |
"""

    # Unique identifiers to force Git to see a change
    run_id = os.getenv("GITHUB_RUN_ID", "local")
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Inject the table AND the schedule into the template
    readme_template = f"""# Training Dashboard
[Click here to view the latest coaching advice & full 18-week plan](./latest_advice.txt)

## Recent Runs
{my_workout_table}

## Hal Higdon Novice 2 Schedule
{novice_2_plan}

*Last updated: {update_time} (UTC) | Run ID: {run_id}*
"""

    # Define absolute path for GitHub runner root
    base_path = os.path.dirname(os.path.abspath(__file__))
    readme_path = os.path.join(base_path, "README.md")

    with open(readme_path, "w") as f:
        f.write(readme_template)
        
    print(f"SUCCESS: Dashboard README updated with {len(recent_runs)} runs and schedule.")

except Exception as e:
    print(f"CRITICAL ERROR updating README: {e}")
