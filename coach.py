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
    # Calculate timestamp for 14 days ago
    two_weeks_ago = int((datetime.now() - timedelta(days=14)).timestamp())
    url = f"https://www.strava.com/api/v3/athlete/activities?after={two_weeks_ago}"
    headers = {'Authorization': f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    return response.json()

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
        "distance_km": round(act['distance'] / 1000, 2),
        "moving_time_min": round(act['moving_time'] / 60, 2),
        "type": act['type']
    })

# --- 3. THE INTELLIGENCE STEP (GEMINI) ---
prompt = f"""
Analyze these Strava activities from the last 2 weeks: {json.dumps(formatted_activities)}

Your task:
1. Specifically comment on the intensity and stats of the most recent activity.
2. Compare the volume and effort of the past week versus the week prior.
3. Based on this data, recommend a structured workout plan for the upcoming week.

Format the output in Markdown. Use bolding and a table for the workout plan.
"""

gemini_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
data = {
    "contents": [{"parts": [{"text": prompt}]}]
}

response = requests.post(gemini_url, json=data)

if response.status_code == 200:
    result = response.json()
    advice = result['candidates'][0]['content']['parts'][0]['text']
    
    with open("latest_advice.txt", "w") as f:
        f.write(advice)
    print("SUCCESS: Analysis generated from live Strava data.")
else:
    print(f"API Error: {response.status_code} - {response.text}")
