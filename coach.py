import os
import requests
import google.generativeai as genai

# 1. Exchange Tokens
auth_res = requests.post("https://www.strava.com/oauth/token", data={
    'client_id': os.getenv('STRAVA_CLIENT_ID'),
    'client_secret': os.getenv('STRAVA_CLIENT_SECRET'),
    'refresh_token': os.getenv('STRAVA_REFRESH_TOKEN'),
    'grant_type': 'refresh_token'
})
access_token = auth_res.json()['access_token']

# 2. Pull activities & ONLY keep what matters (Slimming the data)
header = {'Authorization': f'Bearer {access_token}'}
raw_activities = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=5", headers=header).json()

# We only extract the essentials to save on "Quota/Tokens"
clean_data = []
for a in raw_activities:
    clean_data.append({
        "name": a.get("name"),
        "distance_miles": round(a.get("distance", 0) / 1609.34, 2),
        "moving_time_min": round(a.get("moving_time", 0) / 60, 2),
        "avg_hr": a.get("average_heartrate"),
        "date": a.get("start_date_local")
    })

# 3. Setup Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash-8b') # Using 1.5 Flash is often more stable for free tier

# 4. The Coaching Prompt
prompt = f"Analyze these 5 runs for a marathoner: {clean_data}. Give me a 3-sentence coaching tip."

response = model.generate_content(prompt)
print(response.text)
