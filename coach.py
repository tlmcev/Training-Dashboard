def get_strava_data():
    auth_url = "https://www.strava.com/oauth/token"
    data_url = f"https://www.strava.com/api/v3/athletes/{athlete_id}/stats" # You'll need your athlete ID
    
    # Get a fresh Access Token
    res = requests.post(auth_url, data={
        'client_id': os.environ['STRAVA_CLIENT_ID'],
        'client_secret': os.environ['STRAVA_CLIENT_SECRET'],
        'refresh_token': os.environ['STRAVA_REFRESH_TOKEN'],
        'grant_type': 'refresh_token'
    })
    access_token = res.json()['access_token']
    
    # Get your stats
    header = {'Authorization': f"Bearer {access_token}"}
    stats = requests.get(data_url, headers=header).json()
    return stats['recent_run_totals']['distance'] # Returns meters
    
import requests
import os
import json

# Your API Key from GitHub Secrets
api_key = os.environ["GEMINI_API_KEY"]

# The stable V1 production endpoint
url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"

headers = {
    'Content-Type': 'application/json'
}

data = {
    "contents": [{
        "parts": [{
            "text": f"I ran {miles} miles this week. Given I have a half marathon this Sunday, give me 3 sentences of specific coaching advice."
        }]
    }]
}

response = requests.post(url, headers=headers, data=json.dumps(data))

if response.status_code == 200:
    result = response.json()
    # Digging through the JSON response to get the text
    print(result['candidates'][0]['content']['parts'][0]['text'])
else:
    print(f"Error: {response.status_code}")
    print(response.text)
