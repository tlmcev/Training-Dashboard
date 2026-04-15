import requests
import os
import json

# 1. Setup Variables
miles = 12.5 
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GEMINI_API_KEY is not set.")
    exit(1)

# 2. Set the URL (Using the 2.5 Flash model found in your debug log)
url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={api_key}"

headers = {'Content-Type': 'application/json'}
data = {
    "contents": [{
        "parts": [{"text": f"I ran {miles} miles this week. Give me 3 sentences of specific coaching advice."}]
    }]
}

# 3. Execute
print("Sending request to Gemini 2.5 Flash...")
response = requests.post(url, headers=headers, data=json.dumps(data))
print(f"API Response Status: {response.status_code}")

if response.status_code == 200:
    try:
        result = response.json()
        # Extract the text from the response
        advice = result['candidates'][0]['content']['parts'][0]['text']
        print(f"Advice generated: {advice[:50]}...")
        
        # Write to the file for the Dashboard
        with open("latest_advice.txt", "w") as f:
            f.write(advice)
        print("SUCCESS: latest_advice.txt created.")
        
    except Exception as e:
        print(f"ERROR processing response: {e}")
else:
    print(f"API ERROR Content: {response.text}")
    exit(1)
