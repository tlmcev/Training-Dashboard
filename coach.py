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
        "distance_km": round(act['distance'] / 1000, 2),
        "moving_time_min": round(act['moving_time'] / 60, 2),
        "type": act['type']
    })

# --- 3. THE INTELLIGENCE STEP (GEMINI) ---
# Define the current date/time first
current_time = datetime.now().strftime("%A, %b %d")

# Use an f-string to insert the date and your race context into the prompt
prompt = f"""
Today is {current_time}. 
Note: I am running the Newport Half Marathon this Saturday, April 18th. 

Analyze these Strava activities from the last 2 weeks: {json.dumps(formatted_activities)}

Your task:
1. Specifically comment on the intensity and stats of the most recent activity.
2. Compare the volume and effort of the past week versus the week prior.
3. Based on this data, recommend a structured workout plan for the upcoming week, 
   keeping in mind my race this Saturday.

Format the output in Markdown. Use bolding and a table for the workout plan.
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
