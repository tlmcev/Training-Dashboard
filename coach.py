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
Target: NYC Marathon (Nov 1, 2026) using Hal Higdon Novice 2.
Current Phase: Base Building (plan starts June 29).

USER DATA (Last 14 Days in Miles):
{json.dumps(formatted_activities)}

REFERENCE PLAN (Hal Higdon Novice 2):
{json.dumps(HAL_HIGDON_PLAN)}

Live Strava Data (Last 14 Days): {json.dumps(formatted_activities)}

Instructions for the AI Coach:
MISSION:
1. Compare my Strava miles to the 'Reference Plan' for the current phase.
2. Provide a 3-sentence summary of my progress.
3. Output the FULL 18-week schedule in a Markdown table. 
   - Use the Reference Plan data.
   - Adjust the 'Upcoming' miles ONLY if my recent Strava data shows I am over-training (10% rule).
   - Mark status as ✅ Done, 🏃 Current, or ⏳ Upcoming.
"""

Ensure the table stays formatted in Markdown for the GitHub README.
"""

gemini_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
data = {
    "contents": [{"parts": [{"text": prompt}]}]
}

response = requests.post(gemini_url, json=data)


if response.status_code == 200:
    try:
        result = response.json()
        candidate = result['candidates'][0]
        
        # Check if the response was blocked by safety filters
        if candidate.get('finishReason') == 'SAFETY':
            print("ERROR: Response was blocked by safety filters.")
            exit(1)

        # Gemini 2.5 often includes 'parts'. Let's find the text part.
        content_parts = candidate.get('content', {}).get('parts', [])
        
        # Look specifically for the 'text' key in any of the parts
        advice = next((part['text'] for part in content_parts if 'text' in part), None)

        if advice:
            print(f"Advice generated: {advice[:50]}...")
            with open("latest_advice.txt", "w") as f:
                f.write(advice)
            print("SUCCESS: latest_advice.txt created.")
        else:
            print("ERROR: No text found in the response parts.")
            print(json.dumps(result, indent=2)) # Print the whole thing so we can see the structure
            
    except Exception as e:
        print(f"ERROR processing response: {e}")
        print("Full API Response for debugging:")
        print(json.dumps(response.json(), indent=2))
else:
    print(f"API ERROR: {response.status_code} - {response.text}")
