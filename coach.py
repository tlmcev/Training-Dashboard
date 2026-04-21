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

print(f"STRAVA RESPONSE: {activities}")

formatted_activities = []
for act in activities:
    formatted_activities.append({
    "name": act['name'],
    "date": act['start_date_local'],
    "distance_miles": round(act['distance'] / 1609.34, 2),
    "moving_time_min": round(act['moving_time'] / 60, 2),
    "type": act['type']
})

# --- 3. THE INTELLIGENCE STEP ---
current_time = datetime.now().strftime("%A, %b %d")
marathon_date = datetime(2026, 11, 1)
plan_start_date = marathon_date - timedelta(weeks=18)
run_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

HAL_HIGDON_PLAN = { "Week 1": {"Mon": "Rest", "Tue": "3 mi run", "Wed": "5 mi run", "Thu": "3 mi run", "Fri": "Rest", "Sat": "8 mi run", "Sun": "Cross Train"}, "Week 2": {"Mon": "Rest", "Tue": "3 mi run", "Wed": "5 mi run", "Thu": "3 mi run", "Fri": "Rest", "Sat": "9 mi run", "Sun": "Cross Train"}, "Week 3": {"Mon": "Rest", "Tue": "3 mi run", "Wed": "5 mi run", "Thu": "3 mi run", "Fri": "Rest", "Sat": "6 mi run", "Sun": "Cross Train"}, "Week 4": {"Mon": "Rest", "Tue": "3 mi run", "Wed": "6 mi run", "Thu": "3 mi run", "Fri": "Rest", "Sat": "11 mi run", "Sun": "Cross Train"}, "Week 5": {"Mon": "Rest", "Tue": "3 mi run", "Wed": "6 mi run", "Thu": "3 mi run", "Fri": "Rest", "Sat": "12 mi run", "Sun": "Cross Train"}, "Week 6": {"Mon": "Rest", "Tue": "3 mi run", "Wed": "6 mi run", "Thu": "3 mi run", "Fri": "Rest", "Sat": "9 mi run", "Sun": "Cross Train"}, "Week 7": {"Mon": "Rest", "Tue": "4 mi run", "Wed": "7 mi run", "Thu": "4 mi run", "Fri": "Rest", "Sat": "14 mi run", "Sun": "Cross Train"}, "Week 8": {"Mon": "Rest", "Tue": "4 mi run", "Wed": "7 mi run", "Thu": "4 mi run", "Fri": "Rest", "Sat": "15 mi run", "Sun": "Cross Train"}, "Week 9": {"Mon": "Rest", "Tue": "4 mi run", "Wed": "7 mi run", "Thu": "4 mi run", "Fri": "Rest", "Sat": "Rest", "Sun": "Half Marathon"}, "Week 10": {"Mon": "Rest", "Tue": "4 mi run", "Wed": "8 mi run", "Thu": "4 mi run", "Fri": "Rest", "Sat": "17 mi run", "Sun": "Cross Train"}, "Week 11": {"Mon": "Rest", "Tue": "5 mi run", "Wed": "8 mi run", "Thu": "5 mi run", "Fri": "Rest", "Sat": "18 mi run", "Sun": "Cross Train"}, "Week 12": {"Mon": "Rest", "Tue": "5 mi run", "Wed": "8 mi run", "Thu": "5 mi run", "Fri": "Rest", "Sat": "13 mi run", "Sun": "Cross Train"}, "Week 13": {"Mon": "Rest", "Tue": "5 mi run", "Wed": "5 mi run", "Thu": "5 mi run", "Fri": "Rest", "Sat": "19 mi run", "Sun": "Cross Train"}, "Week 14": {"Mon": "Rest", "Tue": "5 mi run", "Wed": "8 mi run", "Thu": "5 mi run", "Fri": "Rest", "Sat": "12 mi run", "Sun": "Cross Train"}, "Week 15": {"Mon": "Rest", "Tue": "5 mi run", "Wed": "5 mi run", "Thu": "5 mi run", "Fri": "Rest", "Sat": "20 mi run", "Sun": "Cross Train"}, "Week 16": {"Mon": "Rest", "Tue": "5 mi run", "Wed": "4 mi run", "Thu": "5 mi run", "Fri": "Rest", "Sat": "12 mi run", "Sun": "Cross Train"}, "Week 17": {"Mon": "Rest", "Tue": "4 mi run", "Wed": "3 mi run", "Thu": "4 mi run", "Fri": "Rest", "Sat": "8 mi run", "Sun": "Cross Train"}, "Week 18": {"Mon": "Rest", "Tue": "3 mi run", "Wed": "2 mi run", "Thu": "Rest", "Fri": "Rest", "Sat": "2 mi run", "Sun": "Marathon"} }

prompt = f"Today is {current_time}. Strava Data: {json.dumps(formatted_activities)}. Mission: Compare mileage to Base Building goals and output full 18-week Hal Higdon table."

gemini_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
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

            # 2. Build the table using the EXACT variable name from your logs
            # This uses the 'activities' variable we just saw in your terminal!
            my_workout_table = generate_activity_table(activities) 

            # 3. Create the timestamp
            update_time = datetime.now().strftime("%Y-%m-%d %H:%M")

            # 4. OVERWRITE the README entirely (the most reliable way)
            readme_template = f"""# Training Dashboard
[Click here to view the latest coaching advice](./latest_advice.txt)

## Recent Workouts
{my_workout_table}

*Last updated: {update_time}*
"""
            with open("README.md", "w") as f:
                f.write(readme_template)
            
            print(f"SUCCESS: README updated with {len(activities)} activities.")
        else:
            print("ERROR: Gemini response was empty.")
    except Exception as e:
        print(f"ERROR updating README: {e}")
