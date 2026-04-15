import requests
import os
import json

# --- 1. THE DATA VEIN (FETCHING) ---
# For now, we manually set this. 
# Later, your get_strava_data() function will go here.
miles = 12.5 

# --- 2. THE COACH (GEMINI) ---
api_key = os.environ["GEMINI_API_KEY"]
url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"

headers = {'Content-Type': 'application/json'}

# Now 'miles' is defined above, so this f-string will work!
data = {
    "contents": [{
        "parts": [{
            "text": f"I ran {miles} miles this week. Given I have a half marathon this Sunday, give me 3 sentences of specific coaching advice."
        }]
    }]
}

# --- 3. THE EXECUTION ---
response = requests.post(url, headers=headers, data=json.dumps(data))

if response.status_code == 200:
    result = response.json()
    advice = result['candidates'][0]['content']['parts'][0]['text']
    print(advice)
    
    # This part prepares for the "Dashboard View" point we discussed
    with open("latest_advice.txt", "w") as f:
        f.write(advice)
else:
    print(f"Error: {response.status_code}")
