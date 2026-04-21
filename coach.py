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
    output_rows = [
        "| Workout | Distance | Elev. Gain | Avg HR | Date |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]
    for workout in activities_list[:5]:
        name = workout.get('name', 'Unknown')
        dist = round(workout.get('distance', 0) / 1609.34, 2)
        elev = f"{workout.get('total_elevation_gain', 0)}m"
        hr = f"{int(workout.get('average_heartrate', 0))} bpm" if workout.get('average_heartrate') else "--"
        date = workout.get('start_date_local', '0000-00-00')[:10]
        row = f"| {name} | {dist} mi | {elev} | {hr} | {date} |"
        output_rows.append(row)
    return "\n".join(output_rows)

# --- 2. DATA ACQUISITION ---
access_token = get_strava_access_token()
activities = get_activities(access_token)

# Process the data FIRST
formatted_activities = []
for act in activities:
    # We only care about Runs for the marathon plan
    if act['type'] == 'Run':
        formatted_activities.append({
            "name": act['name'],
            "date": act['start_date_local'],
            "distance_miles": round(act['distance'] / 1609.34, 2),
            "moving_time_min": round(act['moving_time'] / 60, 2),
            "type": act['type']
        })

# NOW print the count of the list we actually use
print(f"Run n={len(formatted_activities)}") 
print(f"STRAVA RESPONSE: {activities}")


# --- 3. THE INTELLIGENCE STEP ---
current_time = datetime.now().strftime("%A, %b %d")
marathon_date = "November 1, 2026"

# 1. Stronger Prompt for meaningful AI coaching
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

gemini_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
payload = {"contents": [{"parts": [{"text": prompt}]}]}

response = requests.post(gemini_url, json=payload)

if response.status_code == 200:
    try:
        result = response.json()
        advice = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')

        if advice:
            # 1. Save advice text
            with open("latest_advice.txt", "w") as f:
                f.write(advice)

            # 2. Build the table using ONLY the filtered runs
            # We pass 'formatted_activities' here so the README is clean
            my_workout_table = generate_activity_table(formatted_activities) 

            # 3. Create the timestamp
            update_time = datetime.now().strftime("%Y-%m-%d %H:%M")

            # 4. OVERWRITE the README
            readme_template = f"""# Training Dashboard
[Click here to view the latest coaching advice & full 18-week plan](./latest_advice.txt)

## Recent Runs
{my_workout_table}

*Last updated: {update_time}*
"""
            with open("README.md", "w") as f:
                f.write(readme_template)
            
            print(f"SUCCESS: README updated with {len(formatted_activities)} runs.")
        else:
            print("ERROR: Gemini response was empty.")
    except Exception as e:
        print(f"ERROR updating README: {e}")
