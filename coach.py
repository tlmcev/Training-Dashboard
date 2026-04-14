import os
import requests
import google.generativeai as genai

# 1. Exchange the Refresh Token for a temporary Access Token
auth_res = requests.post("https://www.strava.com/oauth/token", data={
    'client_id': os.getenv('STRAVA_CLIENT_ID'),
    'client_secret': os.getenv('STRAVA_CLIENT_SECRET'),
    'refresh_token': os.getenv('STRAVA_REFRESH_TOKEN'),
    'grant_type': 'refresh_token'
})
access_token = auth_res.json()['access_token']

# 2. Pull your activities from the last 7 days
header = {'Authorization': f'Bearer {access_token}'}
# Fetching the 5 most recent activities
activities = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=5", headers=header).json()

# 3. Setup Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.0-flash')

# 4. The Coaching Prompt
prompt = f"""
You are an expert marathon coach. Here are my Strava activities from this week: {activities}

I am training for the NYC Marathon and have a Half Marathon coming up in mid-April. 
Analyze my pace, distance, and heart rate. 
Tell me:
1. Did I stay consistent with my training?
2. Based on my data, what should my focus be for next week?
3. Give me a 'Coach's Tip' for the upcoming half marathon.
Keep it concise and encouraging.
"""

response = model.generate_content(prompt)
print(response.text)
