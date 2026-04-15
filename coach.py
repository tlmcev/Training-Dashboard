import requests
import os
import json

# Define variables
miles = 12.5 
api_key = os.getenv("GEMINI_API_KEY")

# Debug: Check if API Key exists
if not api_key:
    print("ERROR: GEMINI_API_KEY is not set in environment variables.")
    exit(1)

url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
headers = {'Content-Type': 'application/json'}
data = {
    "contents": [{
        "parts": [{"text": f"I ran {miles} miles this week. Give me 3 sentences of specific coaching advice."}]
    }]
}

print("Sending request to Gemini API...")
response = requests.post(url, headers=headers, data=json.dumps(data))
print(f"Response Status Code: {response.status_code}")

if response.status_code == 200:
    try:
        result = response.json()
        advice = result['candidates'][0]['content']['parts'][0]['text']
        print(f"Advice received: {advice[:50]}...") # Print first 50 chars
        
        # Absolute path check
        file_path = os.path.join(os.getcwd(), "latest_advice.txt")
        print(f"Writing to: {file_path}")
        
        with open(file_path, "w") as f:
            f.write(advice)
        print("File write successful.")
    except Exception as e:
        print(f"Error processing response: {e}")
else:
    print(f"API Error: {response.text}")
