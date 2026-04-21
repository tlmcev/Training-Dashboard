import requests
import os
import json
from datetime import datetime, timedelta

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
    
    # DEBUG: See what Strava is actually saying
    data = response.json()
    if isinstance(data, dict) and 'errors' in data:
        print(f"STRAVA API ERROR: {data}")
        exit(1)
        
    return data

# --- 2. DATA ACQUISITION ---
access_token = get_strava_access_token()
activities = get_activities(access_token)

# Format the data for the prompt
# We focus on name, distance (converted to km), and moving time
formatted_activities = []
for act in activities:
    formatted_activities.append({
    "name": act['name'],
    "date": act['start_date_local'],
    "distance_miles": round(act['distance'] / 1609.34, 2), # Updated conversion
    "moving_time_min": round(act['moving_time'] / 60, 2),
    "type": act['type']
})

# --- 3. THE INTELLIGENCE STEP (GEMINI) ---
# Define the current date/time first
current_time = datetime.now().strftime("%A, %b %d")
marathon_date = datetime(2026, 11, 1)
plan_start_date = marathon_date - timedelta(weeks=18) # June 29, 2026
days_until_start = (plan_start_date - datetime.now()).days

HAL_HIGDON_PLAN = {
    "Week 1": {"Mon": "Rest", "Tue": "3 mi run", "Wed": "5 mi run", "Thu": "3 mi run", "Fri": "Rest", "Sat": "8 mi run", "Sun": "Cross Train"},
    "Week 2": {"Mon": "Rest", "Tue": "3 mi run", "Wed": "5 mi run", "Thu": "3 mi run", "Fri": "Rest", "Sat": "9 mi run", "Sun": "Cross Train"},
    "Week 3": {"Mon": "Rest", "Tue": "3 mi run", "Wed": "5 mi run", "Thu": "3 mi run", "Fri": "Rest", "Sat": "6 mi run", "Sun": "Cross Train"},
    "Week 4": {"Mon": "Rest", "Tue": "3 mi run", "Wed": "6 mi run", "Thu": "3 mi run", "Fri": "Rest", "Sat": "11 mi run", "Sun": "Cross Train"},
    "Week 5": {"Mon": "Rest", "Tue": "3 mi run", "Wed": "6 mi run", "Thu": "3 mi run", "Fri": "Rest", "Sat": "12 mi run", "Sun": "Cross Train"},
    "Week 6": {"Mon": "Rest", "Tue": "3 mi run", "Wed": "6 mi run", "Thu": "3 mi run", "Fri": "Rest", "Sat": "9 mi run", "Sun": "Cross Train"},
    "Week 7": {"Mon": "Rest", "Tue": "4 mi run", "Wed": "7 mi run", "Thu": "4 mi run", "Fri": "Rest", "Sat": "14 mi run", "Sun": "Cross Train"},
    "Week 8": {"Mon": "Rest", "Tue": "4 mi run", "Wed": "7 mi run", "Thu": "4 mi run", "Fri": "Rest", "Sat": "15 mi run", "Sun": "Cross Train"},
    "Week 9": {"Mon": "Rest", "Tue": "4 mi run", "Wed": "7 mi run", "Thu": "4 mi run", "Fri": "Rest", "Sat": "Rest", "Sun": "Half Marathon"},
    "Week 10": {"Mon": "Rest", "Tue": "4 mi run", "Wed": "8 mi run", "Thu": "4 mi run", "Fri": "Rest", "Sat": "17 mi run", "Sun": "Cross Train"},
    "Week 11": {"Mon": "Rest", "Tue": "5 mi run", "Wed": "8 mi run", "Thu": "5 mi run", "Fri": "Rest", "Sat": "18 mi run", "Sun": "Cross Train"},
    "Week 12": {"Mon": "Rest", "Tue": "5 mi run", "Wed": "8 mi run", "Thu": "5 mi run", "Fri": "Rest", "Sat": "13 mi run", "Sun": "Cross Train"},
    "Week 13": {"Mon": "Rest", "Tue": "5 mi run", "Wed": "5 mi run", "Thu": "5 mi run", "Fri": "Rest", "Sat": "19 mi run", "Sun": "Cross Train"},
    "Week 14": {"Mon": "Rest", "Tue": "5 mi run", "Wed": "8 mi run", "Thu": "5 mi run", "Fri": "Rest", "Sat": "12 mi run", "Sun": "Cross Train"},
    "Week 15": {"Mon": "Rest", "Tue": "5 mi run", "Wed": "5 mi run", "Thu": "5 mi run", "Fri": "Rest", "Sat": "20 mi run", "Sun": "Cross Train"},
    "Week 16": {"Mon": "Rest", "Tue": "5 mi run", "Wed": "4 mi run", "Thu": "5 mi run", "Fri": "Rest", "Sat": "12 mi run", "Sun": "Cross Train"},
    "Week 17": {"Mon": "Rest", "Tue": "4 mi run", "Wed": "3 mi run", "Thu": "4 mi run", "Fri": "Rest", "Sat": "8 mi run", "Sun": "Cross Train"},
    "Week 18": {"Mon": "Rest", "Tue": "3 mi run", "Wed": "2 mi run", "Thu": "Rest", "Fri": "Rest", "Sat": "2 mi run", "Sun": "Marathon"},
}

# Use an f-string to insert the date and your race context into the prompt
run_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

prompt = f"""
Run Timestamp: {run_timestamp}
Today is {current_time}.
Phase: Base Building (Pre-Marathon Plan). 
Official 18-week plan starts: June 29.

USER DATA (Last 14 Days in Miles):
{json.dumps(formatted_activities)}

REFERENCE PLAN (Hal Higdon Novice 2):
{json.dumps(HAL_HIGDON_PLAN)}

Live Strava Data (Last 14 Days): {json.dumps(formatted_activities)}

Instructions for the AI Coach:
MISSION:
1. ANALYSIS: Compare my actual Strava mileage to the goal of "Base Building" (maintaining 12-20 miles/week).
2. ADAPTATION: Look at my most recent Strava posts (maximum four per week). If I'm recovering (fewer posts per week), suggest lower intensity. 
    - Specifically comment on the intensity and stats of the most recent activity.
    - Compare the volume and effort of the past week versus the week prior.
3. RECOMMEND: recommend a structured weeklong workout plan for the upcoming week, keeping in mind my "Base Building" phase. 
4. THE TABLE: Output the full 18-week schedule. 
   - CRITICAL: If my recent mileage is significantly lower than the Hal Higdon Novice 2 plan, adjust future mileage in table to avoid injury.
   - If I'm hitting my goals, keep the table as is.
5. FORMAT: 3-5 sentences of coaching followed by the week of training recommendations, finishing with the Markdown table.

Ensure the table stays formatted in Markdown for the GitHub README.
"""

gemini_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
data = {
    "contents": [{"parts": [{"text": prompt}]}]
}

response = requests.post(gemini_url, json=data)
        
    # ...and then we actually RUN the logic OUTSIDE the function (flush with the 'def')
if response.status_code == 200:
    try:  # LEVEL 1
        result = response.json()
        # Adjusted parsing to be safer
        advice = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')

        def generate_activity_table(activities):
            table = "### Recent Strava Activities\n"
            table += "| Workout | Distance | Elev. Gain | Avg HR | Date |\n"
            table += "| :--- | :--- | :--- | :--- | :--- |\n"
            for act in activities[:5]:
                elev = f"{act.get('total_elevation_gain', 0)}m"
                hr = f"{int(act.get('average_heartrate', 0))} bpm" if act.get('average_heartrate') else "--"
                table += f"| {act['name']} | {round(act['distance'] / 1609.34, 2)} mi | {elev} | {hr} | {act['start_date_local'][:10]} |\n"
            return table
            
        if advice:  # LEVEL 2
            print(f"Advice generated: {advice[:50]}...")
            with open("latest_advice.txt", "w") as f:
                f.write(advice)

            strava_table = generate_activity_table(activities) 

            try: # LEVEL 3
                with open("README.md", "r") as f:
                    readme_content = f.read()

                if "" in readme_content:
                    pattern = r".*?"
                    replacement = f"\n{strava_table}\n"
                    new_readme = re.sub(pattern, replacement, readme_content, flags=re.DOTALL)
                    
                    with open("README.md", "w") as f:
                        f.write(new_readme)
                    print("SUCCESS: README.md updated.")
                else:
                    print("ERROR: Placeholder tags missing from README.md")

            except Exception as e: # LEVEL 3 MATCH
                print(f"Error updating README file: {e}")
                
        else: # LEVEL 2 MATCH
            print("ERROR: No advice text found in response.")

    except Exception as e: # LEVEL 1 MATCH
        print(f"ERROR processing API response: {e}")

def generate_activity_table(activities):
    table = "| Workout | Distance | Elev. Gain | Avg HR | Date |\n"
    table += "| :--- | :--- | :--- | :--- | :--- |\n"
    
    for act in activities[:5]:  # Just show the last 5
        # Note: Strava API names for these are 'total_elevation_gain' and 'average_heartrate'
        elev = f"{act.get('total_elevation_gain', 0)}m"
        hr = f"{int(act.get('average_heartrate', 0))} bpm" if act.get('average_heartrate') else "--"
        
        table += f"| {act['name']} | {act['distance_miles']} mi | {elev} | {hr} | {act['date'][:10]} |\n"
    return table

# Read your current README
with open("README.md", "r") as f:
    readme_content = f.read()

# Replace the text between the placeholders
import re
new_readme = re.sub(
    r".*?",
    f"\n{generate_activity_table}\n",
    readme_content,
    flags=re.DOTALL
)

# Save it back
with open("README.md", "w") as f:
    f.write(new_readme)
