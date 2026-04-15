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
        "parts": [{"text": "Analyze my recent Strava data and give me 3 sentences of coaching advice."}]
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
