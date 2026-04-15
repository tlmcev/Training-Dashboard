import requests
import os
import json

# Define variables
miles = 12.5 
api_key = os.getenv("GEMINI_API_KEY")

# CHECKPOINT 1: API Key
if not api_key:
    print("ERROR: GEMINI_API_KEY is missing from the environment.")
    exit(1)
# Change 'v1' to 'v1beta'
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
headers = {'Content-Type': 'application/json'}
data = {
    "contents": [{
        "parts": [{"text": f"I ran {miles} miles this week. Give me 3 sentences of specific coaching advice."}]
    }]
}

# CHECKPOINT 2: API Request
print("Sending request to Gemini...")
response = requests.post(url, headers=headers, data=json.dumps(data))
print(f"API Response Status: {response.status_code}")

# CHECKPOINT 3: File Writing
if response.status_code == 200:
    try:
        result = response.json()
        advice = result['candidates'][0]['content']['parts'][0]['text']
        
        # We use an absolute path to ensure it's in the root
        file_path = os.path.join(os.getcwd(), "latest_advice.txt")
        print(f"Attempting to write file to: {file_path}")
        
        with open(file_path, "w") as f:
            f.write(advice)
        print("SUCCESS: File 'latest_advice.txt' has been created.")
        
    except Exception as e:
        print(f"ERROR: Failed to process JSON or write file: {e}")
else:
    print(f"ERROR: API returned {response.status_code}. Content: {response.text}")
